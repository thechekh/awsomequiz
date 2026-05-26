"""AWSomeQuiz entry point.

Two responsibilities:
1. Handle auth callbacks (?code= from OAuth, ?token_hash= from email links)
   and turn them into a stored session before any page renders.
2. Build the navigation: authenticated users see Home / Account; anonymous
   users see Sign in (nav hidden so they can't get to anything else).
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

import extra_streamlit_components as stx

from app.auth import (
    COOKIE_MANAGER_KEY,
    apply_session_to_client,
    exchange_code,
    get_session,
    restore_session_from_cookie,
    sign_out,
    verify_otp,
)
from app.queries import get_clf_certification, get_practice_streak, get_user_stats_summary
from app.styles import CUSTOM_CSS, DARK_OVERRIDE_CSS, github_link_fix_html

DARK_MODE_KEY = "dark_mode"
DARK_MODE_COOKIE = "awsomequiz_dark"


def _render_sidebar_mini_stats(session: dict) -> None:
    """Compact dark stats panel at the top of the sidebar.

    Shows the two highest-signal stats: overall accuracy + current streak.
    Both helpers are @st.cache_data(ttl=30), so the cost is one cached lookup
    per ~30s rather than a DB round-trip per rerun.
    """
    try:
        cert = get_clf_certification()
        if not cert:
            return
        summary = get_user_stats_summary(session["user"]["id"], cert["id"])
        streak = get_practice_streak(session["user"]["id"])
    except Exception:  # noqa: BLE001 - panel is decorative, never block render
        return

    accuracy = summary.get("overall_accuracy_pct", 0)
    seen = summary.get("unique_seen", 0)
    streak_text = f"{streak}d"
    st.sidebar.markdown(
        f"""
        <div class="sidebar-mini-stats">
          <div class="sidebar-mini-row">
            <span class="sidebar-mini-label">Accuracy</span>
            <span class="sidebar-mini-value">{accuracy}%</span>
          </div>
          <div class="sidebar-mini-row">
            <span class="sidebar-mini-label">Streak</span>
            <span class="sidebar-mini-value">{streak_text}</span>
          </div>
          <div class="sidebar-mini-row">
            <span class="sidebar-mini-label">Seen</span>
            <span class="sidebar-mini-value">{seen}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.set_page_config(
    page_title="AWSomeQuiz",
    page_icon="AWS",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject the global CSS once; cheap and idempotent across reruns.
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# CookieManager is a Streamlit widget; it has to be instantiated at the top
# of every script run (not inside a cached function). We stash the instance
# in session_state so app/auth.py helpers can read/write cookies without
# re-declaring the widget (which would duplicate the key).
cookie_manager = stx.CookieManager(key="awsomequiz_cookies")
st.session_state[COOKIE_MANAGER_KEY] = cookie_manager

# Dark-mode preference: try cookie first (so the choice survives reloads),
# fall back to whatever's in session_state, default light.
if DARK_MODE_KEY not in st.session_state:
    try:
        cookie_val = cookie_manager.get(DARK_MODE_COOKIE)
        st.session_state[DARK_MODE_KEY] = (cookie_val == "1")
    except Exception:  # noqa: BLE001 - cookie not yet ready on first render
        st.session_state[DARK_MODE_KEY] = False

if st.session_state.get(DARK_MODE_KEY):
    st.markdown(DARK_OVERRIDE_CSS, unsafe_allow_html=True)

# Rewrite st.link_button's target so the GitHub OAuth link stays in the
# same tab (link_button defaults to target=_blank). Invisible iframe.
components.html(github_link_fix_html(), height=0)


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

# If st.session_state has no session (e.g. after a page reload, which wipes
# session_state on Streamlit Cloud), try to restore from the refresh-token
# cookie. No-op if the cookie isn't present.
restore_session_from_cookie()

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
        # Guest practice -- reachable via the button on the Login page or
        # by direct URL. Hidden from nav too (nothing else routes here).
        st.Page("pages/guest_practice.py", title="Practice as guest", url_path="guest_practice"),
    ]

pg = st.navigation(pages, position="sidebar" if session else "hidden")

# Dark mode toggle: rendered at top-right of every page via st.columns so the
# layout is stable across toggles (DARK_OVERRIDE_CSS only changes colors,
# not dimensions). Persists via cookie so the preference survives reloads.
_, toggle_col = st.columns([9, 2])
with toggle_col:
    new_dark = st.toggle(
        "Dark mode",
        value=st.session_state.get(DARK_MODE_KEY, False),
        key="dark_mode_toggle",
    )
if new_dark != st.session_state.get(DARK_MODE_KEY):
    st.session_state[DARK_MODE_KEY] = new_dark
    try:
        from datetime import datetime, timedelta, timezone
        cookie_manager.set(
            DARK_MODE_COOKIE,
            "1" if new_dark else "0",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            key="dark_mode_cookie_set",
        )
    except Exception:  # noqa: BLE001 - cookie failure is non-fatal
        pass
    st.rerun()

# Sidebar contents for authenticated users: a compact dark stats panel + the
# signed-in label + sign-out. Lives here (not in each page) so it survives
# navigation. Stats queries are @st.cache_data(ttl=30) so the fetch is cheap.
if session:
    with st.sidebar:
        _render_sidebar_mini_stats(session)
        st.divider()
        user_email = session["user"]["email"] if session.get("user") else "(unknown)"
        st.caption(f"Signed in as **{user_email}**")
        if st.button("Sign out", use_container_width=True, key="sidebar_signout"):
            sign_out()
            st.rerun()

pg.run()
