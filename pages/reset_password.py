"""Password reset target page.

Reached two ways:
1. From the email link sent by `reset_password_request()`. streamlit_app.py
   processes the `token_hash` + `type=recovery` query params, establishes a
   recovery session, then routes here (and leaves `?type=recovery` in the URL
   so we know we're in reset mode).
2. Directly by URL (e.g. user pastes /reset_password). No session = nothing to
   reset; we bounce them to /login.
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user, update_password


def _friendly_error(exc: Exception) -> str:
    msg = getattr(exc, "message", None) or str(exc) or "Could not update password."
    return msg.strip().capitalize()


st.title("Set a new password")

user = current_user()
if not user:
    st.error(
        "No active reset session. Open the password-reset email link again, "
        "or request a new one from the Sign-in page."
    )
    if st.button("Back to sign in"):
        st.switch_page("pages/login.py")
    st.stop()

apply_session_to_client()
st.caption(f"Resetting password for **{user['email']}**")

with st.form("reset_form", clear_on_submit=True):
    new_pw = st.text_input("New password", type="password", autocomplete="new-password")
    new_pw_confirm = st.text_input("Confirm new password", type="password", autocomplete="new-password")
    submitted = st.form_submit_button("Update password", type="primary", use_container_width=True)

if submitted:
    if not new_pw or len(new_pw) < 8:
        st.error("Password must be at least 8 characters.")
    elif new_pw != new_pw_confirm:
        st.error("Passwords do not match.")
    else:
        try:
            update_password(new_pw)
            st.query_params.clear()
            st.success("Password updated. You're now signed in.")
            if st.button("Go to home"):
                st.switch_page("pages/home.py")
        except Exception as exc:  # noqa: BLE001
            st.error(_friendly_error(exc))
