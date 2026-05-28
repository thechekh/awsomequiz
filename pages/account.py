"""Account page: profile (username + preferences) and change-password form."""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user, sign_out, update_password
from app.db import get_supabase
from app.queries import set_theme_preference
from app.theme import (
    THEME_DARK_HC,
    THEME_DARK_SLATE,
    THEME_LABELS,
    THEME_LIGHT,
    THEME_SYSTEM,
    VALID_THEMES,
)


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
    .select("username, preferences, created_at, theme_preference")
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
# Appearance / theme (persists to profiles.theme_preference + a cookie so
# the next browser-only visit uses the same choice before the profile
# fetch can land).
# ---------------------------------------------------------------------------

st.subheader("Appearance")

current_theme = (profile or {}).get("theme_preference") or st.session_state.get(
    "theme_preference"
) or THEME_SYSTEM
if current_theme not in VALID_THEMES:
    current_theme = THEME_SYSTEM

theme_options = [THEME_SYSTEM, THEME_LIGHT, THEME_DARK_SLATE, THEME_DARK_HC]
chosen_theme = st.radio(
    "Theme",
    options=theme_options,
    format_func=lambda k: THEME_LABELS.get(k, k),
    index=theme_options.index(current_theme),
    horizontal=False,
    key="theme_radio",
    help=(
        "System default follows your OS / browser preference. "
        "Neutral Slate is the comfortable dark; High Contrast is the deeper "
        "dark with punchier feedback colors."
    ),
)

if chosen_theme != current_theme:
    try:
        set_theme_preference(user["id"], chosen_theme)
        st.session_state["theme_preference"] = chosen_theme
        st.session_state["_pending_theme_cookie_write"] = chosen_theme
        st.success("Theme updated.")
        st.rerun()
    except Exception as exc:  # noqa: BLE001
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
