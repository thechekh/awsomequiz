"""AWSomeQuiz entry point.

Two responsibilities:
1. Handle auth callbacks (?code= from OAuth, ?token_hash= from email links)
   and turn them into a stored session before any page renders.
2. Build the navigation: authenticated users see Home / Account; anonymous
   users see Sign in (nav hidden so they can't get to anything else).
"""

from __future__ import annotations

import streamlit as st

from app.auth import (
    apply_session_to_client,
    exchange_code,
    get_session,
    sign_out,
    verify_otp,
)

st.set_page_config(
    page_title="AWSomeQuiz",
    page_icon="AWS",
    layout="wide",
    initial_sidebar_state="expanded",
)


AUTH_CALLBACK_ERROR_KEY = "auth_callback_error"


def _handle_auth_callback() -> None:
    """Convert auth callback URL params into a session, then clean the URL.

    Stores any failure message in st.session_state[AUTH_CALLBACK_ERROR_KEY]
    so the Login page can render it on the next render pass.
    """
    params = st.query_params

    code = params.get("code")
    if code:
        result = exchange_code(code)
        st.query_params.clear()
        if result is None:
            st.session_state[AUTH_CALLBACK_ERROR_KEY] = (
                "Sign-in callback failed (the link may have expired). Please try again."
            )
        st.rerun()

    token_hash = params.get("token_hash")
    otp_type = params.get("type")
    if token_hash and otp_type:
        try:
            verify_otp(token_hash, otp_type)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001 - keep going; user may still be able to recover
            st.session_state[AUTH_CALLBACK_ERROR_KEY] = (
                f"Could not verify link: {exc}. Try requesting a new one."
            )
            st.query_params.clear()
            st.rerun()
            return  # unreachable, but mypy + clarity

        if otp_type == "recovery":
            # Preserve type=recovery (drops token_hash so back-button can't replay).
            st.query_params.clear()
            st.query_params["type"] = "recovery"
            st.switch_page("pages/reset_password.py")
        else:
            st.query_params.clear()
            st.rerun()


_handle_auth_callback()

session = get_session()
apply_session_to_client()

if session:
    pages = [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True, url_path=""),
        st.Page("pages/practice.py", title="Practice", icon=":material/quiz:", url_path="practice"),
        st.Page("pages/timed_exam.py", title="Timed exam", icon=":material/timer:", url_path="timed_exam"),
        st.Page("pages/review.py", title="Review", icon=":material/replay:", url_path="review"),
        st.Page("pages/bookmarks.py", title="Bookmarks", icon=":material/bookmark:", url_path="bookmarks"),
        st.Page("pages/flashcards.py", title="Flashcards", icon=":material/style:", url_path="flashcards"),
        st.Page("pages/stats.py", title="Stats", icon=":material/insights:", url_path="stats"),
        st.Page("pages/account.py", title="Account", icon=":material/person:", url_path="account"),
    ]
else:
    pages = [
        st.Page("pages/login.py", title="Sign in", icon=":material/login:", default=True, url_path=""),
        # Hidden from nav (position="hidden" below) but URL-routable so the
        # password-reset email link works.
        st.Page("pages/reset_password.py", title="Reset password", url_path="reset_password"),
    ]

pg = st.navigation(pages, position="sidebar" if session else "hidden")

# Sidebar sign-out for authenticated users. Lives here (not in each page) so
# it survives navigation without each page having to render it.
if session:
    with st.sidebar:
        st.divider()
        user_email = session["user"]["email"] if session.get("user") else "(unknown)"
        st.caption(f"Signed in as **{user_email}**")
        if st.button("Sign out", use_container_width=True, key="sidebar_signout"):
            sign_out()
            st.rerun()

pg.run()
