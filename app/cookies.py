"""First-party cookie I/O for Streamlit Cloud.

The CookieManager from extra-streamlit-components is unusable here -- its
React chunk aborts on Streamlit Cloud (net::ERR_ABORTED), so writes never
land. AND Streamlit Cloud's reverse proxy strips the Cookie request header
before the WebSocket upgrade reaches the app, so st.context.headers is
useless for reads in prod.

Workarounds in this module:
 - write/delete: inject inline JS via `st.html(unsafe_allow_javascript=True)`,
   which embeds the script directly into the parent page DOM (no iframe).
   document.cookie writes therefore land on the top-level awsomequiz.streamlit.app
   origin synchronously when the script tag mounts.
 - read: the cookie_reader custom component (Streamlit declare_component) reads
   document.cookie inside its iframe and sends the value back via the standard
   component-value postMessage protocol. No top-navigation needed (which the
   components.html sandbox blocked).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components

_COOKIE_READER_DIR = Path(__file__).parent / "cookie_reader"
_cookie_reader = components.declare_component(
    "awsomequiz_cookie_reader",
    path=str(_COOKIE_READER_DIR),
)


def write_cookie(name: str, value: str, max_age_days: int) -> None:
    """Set a first-party cookie via inline JS injection."""
    st.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            const v = encodeURIComponent({json.dumps(value)});
            document.cookie = k + "=" + v
                + "; max-age={int(max_age_days * 86400)}"
                + "; path=/; SameSite=Lax; Secure";
        }} catch (e) {{}}
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def delete_cookie(name: str) -> None:
    """Clear a first-party cookie by setting max-age=0."""
    st.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            document.cookie = k + "=; max-age=0; path=/; SameSite=Lax; Secure";
        }} catch (e) {{}}
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def read_cookie_client_side(cookie_name: str, *, key: str | None = None) -> str | None:
    """Read a first-party cookie via the cookie_reader custom component.

    Returns None on the first script run (component hasn't sent its value yet),
    then the actual value on the rerun the component triggers via postMessage.
    No top-navigation needed, so the components.html sandbox limitation that
    blocks a URL-hop approach doesn't apply here.
    """
    return _cookie_reader(cookie_name=cookie_name, default=None, key=key)


def read_cookie_from_headers(name: str) -> str | None:
    """Read a cookie from the live request headers (works in local dev, not
    on Streamlit Cloud where the proxy strips the Cookie header)."""
    try:
        headers = st.context.headers
    except Exception:  # noqa: BLE001 - context may not be ready in tests
        return None
    cookie_header = headers.get("Cookie") or headers.get("cookie") or ""
    for chunk in cookie_header.split(";"):
        chunk = chunk.strip()
        if chunk.startswith(f"{name}="):
            return unquote(chunk[len(name) + 1:])
    return None
