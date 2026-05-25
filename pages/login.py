"""Login page. Three tabs: Sign in / Register / Forgot password.

Plus a "Sign in with Google" button that's only enabled if the Supabase Google
provider is configured. If it isn't, the button shows a help caption pointing
to the setup steps.
"""

from __future__ import annotations

import streamlit as st

from app.auth import (
    get_google_oauth_url,
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
# Google OAuth button (top of page, above tabs)
# ---------------------------------------------------------------------------

google_url = get_google_oauth_url()
oauth_col, _ = st.columns([1, 1])
with oauth_col:
    if google_url:
        st.link_button(
            "Sign in with Google",
            google_url,
            use_container_width=True,
            icon=":material/account_circle:",
        )
    else:
        st.button(
            "Sign in with Google (not configured)",
            use_container_width=True,
            disabled=True,
            help=(
                "Google OAuth isn't enabled in this Supabase project. "
                "Set `[auth.external.google] enabled = true` in `supabase/config.toml`, "
                "fill `SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID` / `_SECRET` in `.env`, "
                "then `supabase stop && supabase start`."
            ),
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
