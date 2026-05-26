"""Login page. Three tabs: Sign in / Register / Forgot password.

Plus a "Sign in with GitHub" button at the top. The button renders whenever
supabase-py returns an OAuth URL (which it always does, regardless of whether
GitHub is configured server-side) -- so configure the provider in Supabase
dashboard before publishing this page; otherwise users will see a 400 error
from Supabase on click.
"""

from __future__ import annotations

import streamlit as st

from app.auth import (
    get_github_oauth_url,
    reset_password_request,
    sign_in,
    sign_up,
)


def _friendly_error(exc: Exception) -> str:
    """Return a user-facing message from a Supabase / gotrue error."""
    msg = getattr(exc, "message", None) or str(exc) or "Authentication failed."
    return msg.strip().capitalize()


# GitHub's official Octicons mark-github-16 SVG. Inline so we don't depend on
# external fonts/CDNs and Streamlit's Material Symbols set (which has no
# brand logos) doesn't have to ship it.
GITHUB_LOGO_SVG = (
    '<svg viewBox="0 0 16 16" width="18" height="18" fill="currentColor" '
    'aria-hidden="true"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 '
    '7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 '
    '1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 '
    '0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-'
    '.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 '
    '3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-'
    '1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 '
    '.67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 '
    '8-8Z"/></svg>'
)


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
        # target="_top" breaks out of Streamlit's component iframe -- without
        # it the browser tries to load github.com *inside* the iframe and
        # GitHub's frame-ancestors CSP blocks it.
        st.markdown(
            f'<a href="{github_url}" class="github-signin-btn" target="_top" '
            f'rel="noopener noreferrer">'
            f'{GITHUB_LOGO_SVG}<span>Sign in with GitHub</span></a>',
            unsafe_allow_html=True,
        )
    st.divider()

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
