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


st.title("AWSomeQuiz")
st.caption("Sign in to start practicing.")

# Surface and clear any auth-callback error that streamlit_app.py left for us
# (e.g. a stale OAuth code or an expired email-verification link).
if callback_err := st.session_state.pop("auth_callback_error", None):
    st.error(callback_err)

# Note: cert selection for guests happens on the Guest Practice page itself
# (after they click "Practice as guest"), not here -- keeps the Login page
# focused on auth. Logged-in users switch via the sidebar picker.

# ---------------------------------------------------------------------------
# GitHub OAuth button (centered above the tabs)
# ---------------------------------------------------------------------------

github_url = get_github_oauth_url()
if github_url:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        # st.link_button defaults to target="_blank" (new tab). The OAuth
        # flow completes in the new tab and the user is signed in there.
        # We tried popup-based same-tab UX -- it kept failing because
        # cookie persistence across the popup/parent boundary races the
        # popup close. Default new-tab is the proven working path.
        st.link_button(
            "Sign in with GitHub",
            github_url,
            width="stretch",
        )
    st.divider()

# Guest mode -- try the practice runner without an account. No progress saved.
_, gmid, _ = st.columns([1, 2, 1])
with gmid:
    if st.button("Practice as guest (no signup)", width="stretch", key="guest_cta"):
        st.switch_page("pages/guest_practice.py")
    if st.button("Browse glossary", width="stretch", key="glossary_cta"):
        st.switch_page("pages/glossary.py")

signin_tab, register_tab, forgot_tab = st.tabs(["Sign in", "Register", "Forgot password"])

# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------

with signin_tab:
    with st.form("signin_form", clear_on_submit=False):
        email = st.text_input("Email", key="signin_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="signin_password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
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
        submitted = st.form_submit_button("Create account", type="primary", width="stretch")
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
                        f"Account created for **{email}**. Check your email "
                        "(including the spam folder) for the verification link."
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
        submitted = st.form_submit_button("Send reset link", width="stretch")
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
                    "Check your inbox (and the spam folder)."
                )
