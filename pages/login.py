"""Login page. Three tabs: Sign in / Register / Forgot password.

Plus a "Sign in with GitHub" button at the top. The button renders whenever
supabase-py returns an OAuth URL (which it always does, regardless of whether
GitHub is configured server-side) -- so configure the provider in Supabase
dashboard before publishing this page; otherwise users will see a 400 error
from Supabase on click.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from app.auth import (
    DARK_MODE_KEY,
    get_github_oauth_url,
    reset_password_request,
    sign_in,
    sign_up,
)


def _friendly_error(exc: Exception) -> str:
    """Return a user-facing message from a Supabase / gotrue error."""
    msg = getattr(exc, "message", None) or str(exc) or "Authentication failed."
    return msg.strip().capitalize()


st.title("AWSomeQuiz")
st.caption("Sign in to start practicing.")

# Surface and clear any auth-callback error that streamlit_app.py left for us
# (e.g. a stale OAuth code or an expired email-verification link).
if callback_err := st.session_state.pop("auth_callback_error", None):
    st.error(callback_err)

# ---------------------------------------------------------------------------
# GitHub OAuth button (centered above the tabs)
# ---------------------------------------------------------------------------

github_url = get_github_oauth_url()
if github_url:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        # Render via components.html (NOT st.markdown) because Streamlit's
        # markdown pipeline routes raw HTML through React. React converts
        # `onclick="..."` to its `onClick` prop and rejects string handlers
        # (React error #231). components.html renders inside a real iframe
        # where addEventListener works as plain JS.
        #
        # Popup-OAuth: opens GitHub in a popup (top-level browsing context,
        # so no iframe/CSP issues). When the popup closes, the parent tab
        # reloads and picks up the new session via the refresh-token cookie.
        dark = bool(st.session_state.get(DARK_MODE_KEY))
        bg = "#1F2937" if dark else "#FFFFFF"
        border = "#374151" if dark else "#D1D5DB"
        color = "#F1F5F9" if dark else "#111827"
        hover_bg = "#374151" if dark else "#FAFAFA"
        hover_border = "#4B5563" if dark else "#9CA3AF"
        components.html(
            f"""
            <!DOCTYPE html>
            <html><head><style>
                html, body {{ margin: 0; padding: 0; background: transparent; }}
                .github-signin-btn {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 0.5rem;
                    width: 100%;
                    padding: 0.55rem 1rem;
                    border-radius: 6px;
                    border: 1px solid {border};
                    background: {bg};
                    color: {color};
                    font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                                 'Segoe UI', system-ui, sans-serif;
                    font-size: 0.875rem;
                    font-weight: 500;
                    text-decoration: none;
                    cursor: pointer;
                    box-sizing: border-box;
                    transition: background 0.15s ease, border-color 0.15s ease;
                }}
                .github-signin-btn:hover {{
                    background: {hover_bg};
                    border-color: {hover_border};
                }}
            </style></head>
            <body>
            <a href="#" id="gh-btn" class="github-signin-btn">
                <svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor"
                     aria-hidden="true"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>
                <span>Sign in with GitHub</span>
            </a>
            <script>
                // BroadcastChannel is the resilient way to signal between
                // popup and parent tab. window.opener gets nulled during
                // the OAuth redirect chain (cross-origin COOP), so opener-
                // based signaling fails. A same-origin BroadcastChannel is
                // not affected by cross-origin navigation history.
                document.getElementById('gh-btn').addEventListener('click', function(e) {{
                    e.preventDefault();
                    const p = window.open(
                        '{github_url}',
                        'github_oauth',
                        'width=600,height=720,resizable=yes,scrollbars=yes'
                    );
                    if (!p) {{
                        alert('Pop-up blocked. Please allow pop-ups for this site and try again.');
                        return;
                    }}

                    let reloaded = false;
                    const ch = new BroadcastChannel('awsomequiz_oauth');
                    const interval = setInterval(checkClosed, 600);

                    function done() {{
                        if (reloaded) return;
                        reloaded = true;
                        try {{ ch.close(); }} catch (_) {{}}
                        clearInterval(interval);
                        try {{ p.close(); }} catch (_) {{}}
                        try {{ window.top.location.reload(); }} catch (_) {{}}
                    }}

                    function checkClosed() {{
                        // Fallback: if BroadcastChannel doesn't fire (older
                        // browsers, or popup closed without dispatching),
                        // detect via popup.closed and reload anyway.
                        try {{ if (p.closed) done(); }} catch (_) {{}}
                    }}

                    ch.addEventListener('message', function(ev) {{
                        if (ev.data === 'oauth_done') done();
                    }});
                }});
            </script>
            </body></html>
            """,
            height=50,
        )
    st.divider()

# Guest mode -- try the practice runner without an account. No progress saved.
_, gmid, _ = st.columns([1, 2, 1])
with gmid:
    if st.button("Practice as guest (no signup)", use_container_width=True, key="guest_cta"):
        st.switch_page("pages/guest_practice.py")

signin_tab, register_tab, forgot_tab = st.tabs(["Sign in", "Register", "Forgot password"])

# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------

with signin_tab:
    with st.form("signin_form", clear_on_submit=False):
        email = st.text_input("Email", key="signin_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="signin_password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
        else:
            try:
                sign_in(email, password)
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - surface Supabase auth error to user
                st.error(_friendly_error(exc))

# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

with register_tab:
    with st.form("register_form", clear_on_submit=False):
        email = st.text_input("Email", key="register_email", autocomplete="email")
        password = st.text_input(
            "Password (min 8 characters)",
            type="password",
            key="register_password",
            autocomplete="new-password",
        )
        password_confirm = st.text_input(
            "Confirm password",
            type="password",
            key="register_password_confirm",
            autocomplete="new-password",
        )
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
        elif password != password_confirm:
            st.error("Passwords do not match.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters.")
        else:
            try:
                result = sign_up(email, password)
                if result.get("needs_confirmation"):
                    st.success(
                        f"Account created for **{email}**. Check your email for the "
                        "verification link. (Locally: http://localhost:54324 --Inbucket.)"
                    )
                else:
                    # No confirmation required -- already signed in.
                    st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(_friendly_error(exc))

# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

with forgot_tab:
    with st.form("forgot_form", clear_on_submit=True):
        email = st.text_input("Email", key="forgot_email", autocomplete="email")
        submitted = st.form_submit_button("Send reset link", use_container_width=True)
    if submitted:
        if not email:
            st.error("Email is required.")
        else:
            try:
                reset_password_request(email)
            except Exception as exc:  # noqa: BLE001
                st.error(_friendly_error(exc))
            else:
                # Always show success even on unknown email, so we don't leak which
                # addresses are registered. Supabase itself follows this pattern.
                st.success(
                    "If an account with that email exists, a reset link has been sent. "
                    "(Locally: check http://localhost:54324 -- Inbucket.)"
                )
