"""Account page: profile (username + preferences) and change-password form."""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user, sign_out, update_password
from app.db import get_supabase


def _friendly_error(exc: Exception) -> str:
    msg = getattr(exc, "message", None) or str(exc) or "Request failed."
    return msg.strip().capitalize()


user = current_user()
if not user:
    st.switch_page("pages/login.py")

apply_session_to_client()
supabase = get_supabase()

st.title("Account")

# ---------------------------------------------------------------------------
# Profile (auto-created by the on_auth_user_created trigger)
# ---------------------------------------------------------------------------

profile = (
    supabase.table("profiles")
    .select("username, preferences, created_at")
    .eq("id", user["id"])
    .single()
    .execute()
).data

st.subheader("Profile")
with st.form("profile_form"):
    st.text_input("Email", value=user["email"], disabled=True)
    new_username = st.text_input(
        "Username",
        value=(profile or {}).get("username") or "",
        help="Shown on the leaderboard once that lands. Must be unique.",
    )
    submitted = st.form_submit_button("Save")

if submitted:
    try:
        (
            supabase.table("profiles")
            .update({"username": new_username or None})
            .eq("id", user["id"])
            .execute()
        )
        st.success("Profile saved.")
    except Exception as exc:  # noqa: BLE001 - surface unique-constraint failures cleanly
        st.error(_friendly_error(exc))

st.divider()

# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

st.subheader("Change password")
with st.form("password_form", clear_on_submit=True):
    new_pw = st.text_input("New password", type="password", autocomplete="new-password")
    new_pw_confirm = st.text_input("Confirm new password", type="password", autocomplete="new-password")
    pw_submitted = st.form_submit_button("Update password")

if pw_submitted:
    if not new_pw or len(new_pw) < 8:
        st.error("Password must be at least 8 characters.")
    elif new_pw != new_pw_confirm:
        st.error("Passwords do not match.")
    else:
        try:
            update_password(new_pw)
            st.success("Password updated.")
        except Exception as exc:  # noqa: BLE001
            st.error(_friendly_error(exc))

st.divider()

# ---------------------------------------------------------------------------
# Sign out (also in sidebar; redundant here for discoverability)
# ---------------------------------------------------------------------------

if st.button("Sign out", type="secondary"):
    sign_out()
    st.rerun()
