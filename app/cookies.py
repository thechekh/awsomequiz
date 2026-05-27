"""First-party cookie I/O for Streamlit Cloud.

The CookieManager from extra-streamlit-components is unusable here -- its
React chunk aborts on Streamlit Cloud (net::ERR_ABORTED), so writes never
land. AND Streamlit Cloud's reverse proxy strips the Cookie request header
before the WebSocket upgrade reaches the app, so st.context.headers is
useless for reads in prod.

Workarounds in this module:
 - write/delete: inject inline JS into a height-0 components.html iframe.
   No external chunks to fetch, so the write is synchronous within the
   iframe load.
 - read: a URL hop. trigger_relay() injects JS that reads document.cookie
   and reloads the page with the value as ?__rt_relay=. read_relay_param()
   picks the value up server-side and clears the param. Each write also
   clears the JS sessionStorage flag so future browser refreshes re-trigger
   the relay.
"""

from __future__ import annotations

import json
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components

RT_RELAY_PARAM = "__rt_relay"
_RELAY_FLAG_JS = "__rt_relay_done"


def write_cookie(name: str, value: str, max_age_days: int) -> None:
    """Set a first-party cookie via inline JS injection."""
    components.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            const v = encodeURIComponent({json.dumps(value)});
            document.cookie = k + "=" + v
                + "; max-age={int(max_age_days * 86400)}"
                + "; path=/; SameSite=Lax; Secure";
            try {{ window.top.sessionStorage.removeItem({json.dumps(_RELAY_FLAG_JS)}); }} catch (e) {{}}
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def delete_cookie(name: str) -> None:
    """Clear a first-party cookie by setting max-age=0."""
    components.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            document.cookie = k + "=; max-age=0; path=/; SameSite=Lax; Secure";
            try {{ window.top.sessionStorage.removeItem({json.dumps(_RELAY_FLAG_JS)}); }} catch (e) {{}}
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def read_relay_param() -> str | None:
    """Pop the value of the ?__rt_relay= query param if present."""
    relay = st.query_params.get(RT_RELAY_PARAM)
    if not relay:
        return None
    st.query_params.pop(RT_RELAY_PARAM, None)
    return unquote(relay)


def trigger_relay(cookie_name: str) -> None:
    """Inject JS that reads document.cookie and reloads with the value as a
    query param. SessionStorage flag prevents loops; write_cookie clears the
    flag so future browser refreshes can re-trigger.
    """
    components.html(
        f"""
        <script>
        (function() {{
            try {{
                const top = window.top;
                if (top.sessionStorage.getItem({json.dumps(_RELAY_FLAG_JS)}) === '1') return;
                top.sessionStorage.setItem({json.dumps(_RELAY_FLAG_JS)}, '1');
                const prefix = {json.dumps(cookie_name + '=')};
                const c = (top.document.cookie || '').split(';')
                    .map(x => x.trim()).find(x => x.startsWith(prefix));
                if (c) {{
                    const v = c.slice(prefix.length);
                    top.location.replace(top.location.pathname + '?{RT_RELAY_PARAM}=' + v);
                }}
            }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
    )


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
