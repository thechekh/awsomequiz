"""AWSomeQuiz entry point.

Two responsibilities:
1. Handle auth callbacks (?code= from OAuth, ?token_hash= from email links)
   and turn them into a stored session before any page renders.
2. Build the navigation: authenticated users see Home / Account; anonymous
   users see Sign in (nav hidden so they can't get to anything else).
"""

from __future__ import annotations

import json
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components

from app.auth import (
    COOKIE_MAX_AGE_DAYS,
    COOKIE_NAME,
    DARK_MODE_KEY,
    PENDING_DELETE_KEY,
    PENDING_SAVE_KEY,
    apply_session_to_client,
    exchange_code,
    get_session,
    restore_session_from_cookie,
    sign_out,
    verify_otp,
)
from app.queries import get_clf_certification, get_practice_streak, get_user_stats_summary
from app.styles import render_combined_css

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

# Cookie I/O bypasses extra-streamlit-components' CookieManager. Its React
# bundle (2.*.chunk.js) reliably aborts on Streamlit Cloud (net::ERR_ABORTED),
# so .set() never reaches a working handler -- confirmed by Playwright:
# neither awsomequiz_rt nor awsomequiz_dark land, even with display:block
# forcing the iframe to stay mounted. Inline JS in components.html has no
# external chunks to fetch, so the write is synchronous and lands before
# any rerun unmounts the iframe. Reads come from st.context.headers, which
# is the live HTTP request and doesn't depend on any iframe loading.

def _write_cookie_via_js(name: str, value: str, max_age_days: int) -> None:
    """Set a first-party cookie by injecting inline JS into a height-0 iframe."""
    components.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            const v = encodeURIComponent({json.dumps(value)});
            document.cookie =
                k + "=" + v + "; max-age={int(max_age_days * 86400)}"
                + "; path=/; SameSite=Lax; Secure";
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def _delete_cookie_via_js(name: str) -> None:
    """Clear a first-party cookie by setting max-age=0 from a same-origin iframe."""
    components.html(
        f"""
        <script>
        try {{
            const k = {json.dumps(name)};
            document.cookie = k + "=; max-age=0; path=/; SameSite=Lax; Secure";
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )


def _read_cookie_from_headers(name: str) -> str | None:
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


_pending_save = st.session_state.pop(PENDING_SAVE_KEY, None)
_pending_delete = st.session_state.pop(PENDING_DELETE_KEY, False)
if _pending_save:
    _write_cookie_via_js(COOKIE_NAME, _pending_save, COOKIE_MAX_AGE_DAYS)
elif _pending_delete:
    _delete_cookie_via_js(COOKIE_NAME)

if DARK_MODE_KEY not in st.session_state:
    st.session_state[DARK_MODE_KEY] = _read_cookie_from_headers(DARK_MODE_COOKIE) == "1"

# Single CSS injection (combines light base + optional dark overrides). This
# matters because toggling dark used to add/remove a SECOND st.markdown,
# whose wrapper shifted page content by ~16px. One injection = stable DOM.
st.markdown(
    render_combined_css(bool(st.session_state.get(DARK_MODE_KEY))),
    unsafe_allow_html=True,
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
    _write_cookie_via_js(DARK_MODE_COOKIE, "1" if new_dark else "0", 365)
    st.rerun()

# Sidebar contents for authenticated users: a compact dark stats panel + the
# signed-in label + sign-out. Lives here (not in each page) so it survives
# navigation. Stats queries are @st.cache_data(ttl=30) so the fetch is cheap.
if session:
    # initial_sidebar_state="expanded" on st.set_page_config only takes
    # effect on cold load. After login (a rerun, not a cold load), the
    # sidebar stays collapsed from the prior position="hidden" unauth
    # render. Poll for the expand button from this iframe and click it
    # once per browser session. components.v1.html is required because
    # st.markdown strips <script>.
    components.html(
        """
        <script>
        (function () {
            const flag = '__awsomequizExpandClicked';
            const findClickable = (doc) => {
                const candidates = [
                    '[data-testid="stExpandSidebarButton"] button',
                    '[data-testid="stExpandSidebarButton"]',
                    'button[data-testid="stExpandSidebarButton"]',
                    '[data-testid="stSidebarCollapsedControl"] button',
                    '[data-testid="collapsedControl"] button',
                ];
                for (const sel of candidates) {
                    const el = doc.querySelector(sel);
                    if (el && (el.tagName === 'BUTTON' || el.querySelector('button') || el.click)) {
                        return el.tagName === 'BUTTON' ? el : (el.querySelector('button') || el);
                    }
                }
                return null;
            };
            const tryExpand = () => {
                try {
                    const doc = window.parent.document;
                    if (window.parent[flag]) return true;
                    const sidebar = doc.querySelector('[data-testid="stSidebar"]');
                    if (sidebar && sidebar.getAttribute('aria-expanded') === 'true') {
                        window.parent[flag] = true;
                        return true;
                    }
                    const btn = findClickable(doc);
                    if (btn) {
                        btn.click();
                        window.parent[flag] = true;
                        return true;
                    }
                } catch (_) { return true; /* cross-origin -- give up silently */ }
                return false;
            };
            if (!tryExpand()) {
                const t = setInterval(() => { if (tryExpand()) clearInterval(t); }, 150);
                setTimeout(() => clearInterval(t), 6000);
            }
        })();
        </script>
        """,
        height=0,
    )
    with st.sidebar:
        _render_sidebar_mini_stats(session)
        st.divider()
        user_email = session["user"]["email"] if session.get("user") else "(unknown)"
        st.caption(f"Signed in as **{user_email}**")
        if st.button("Sign out", use_container_width=True, key="sidebar_signout"):
            sign_out()
            st.rerun()

pg.run()
