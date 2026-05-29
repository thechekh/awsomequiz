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
    COOKIE_MAX_AGE_DAYS,
    COOKIE_NAME,
    PENDING_DELETE_KEY,
    PENDING_SAVE_KEY,
    apply_session_to_client,
    exchange_code,
    get_session,
    restore_session_from_cookie,
    sign_out,
    verify_otp,
)
from app.cookies import (
    delete_cookie,
    read_cookie_from_headers,
    write_cookie,
)
from app.queries import (
    get_current_certification,
    get_display_name,
    get_practice_streak,
    get_theme_preference,
    get_user_stats_summary,
    list_certifications_with_questions,
    set_current_certification,
    set_theme_preference,
)
from app.styles import render_combined_css
from app.theme import (
    THEME_DARK_HC,
    THEME_DARK_SLATE,
    THEME_LIGHT,
    THEME_SYSTEM,
    VALID_THEMES,
    render_theme_css,
)

THEME_COOKIE = "awsomequiz_theme"
THEME_PREF_KEY = "theme_preference"
_PENDING_THEME_WRITE_KEY = "_pending_theme_cookie_write"


def _render_sidebar_cert_picker() -> None:
    """Compact cert switcher at the top of the sidebar.

    Only renders when 2+ certs have question banks loaded -- a single-cert
    deployment doesn't need a selector. Picker writes through to
    set_current_certification (session_state + profiles.current_cert_code)
    and reruns so downstream pages re-read with the new cert.
    """
    available = list_certifications_with_questions()
    if not available:
        return
    current = get_current_certification()
    current_code = current["code"] if current else available[0]["code"]
    if len(available) == 1:
        st.sidebar.caption(f"**{available[0]['code']} — {available[0]['name']}**")
        return
    chosen = st.sidebar.selectbox(
        "Certification",
        options=[c["code"] for c in available],
        format_func=lambda code: f"{code} — {next(c['name'] for c in available if c['code'] == code)}",
        index=next((i for i, c in enumerate(available) if c["code"] == current_code), 0),
        key="sidebar_cert_picker",
    )
    if chosen != current_code:
        set_current_certification(chosen)
        st.rerun()


def _render_sidebar_mini_stats(session: dict) -> None:
    """Compact dark stats panel at the top of the sidebar.

    Shows the two highest-signal stats: overall accuracy + current streak.
    Both helpers are @st.cache_data(ttl=30), so the cost is one cached lookup
    per ~30s rather than a DB round-trip per rerun.
    """
    try:
        cert = get_current_certification()
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
    # "auto": Streamlit shows the sidebar expanded on desktop and collapses
    # it on mobile (<768 px), which is what we want -- an open sidebar on
    # a phone covers 60-70% of the screen.
    initial_sidebar_state="auto",
)

# Drain any queued cookie write/delete BEFORE anything else can call st.rerun().
# Callers (auth flows, dark-mode toggle) queue into session_state instead of
# writing inline because the immediately-following rerun discards UI elements
# (including st.html script injections) registered in the same script run.
# Rendering here, at the top of the file, means the JS lands before the user
# can trigger another rerun.
_pending_save = st.session_state.pop(PENDING_SAVE_KEY, None)
_pending_delete = st.session_state.pop(PENDING_DELETE_KEY, False)
if _pending_save:
    write_cookie(COOKIE_NAME, _pending_save, COOKIE_MAX_AGE_DAYS)
elif _pending_delete:
    delete_cookie(COOKIE_NAME)
_pending_theme = st.session_state.pop(_PENDING_THEME_WRITE_KEY, None)
if _pending_theme is not None:
    write_cookie(THEME_COOKIE, _pending_theme, 365)


def _resolve_theme_pref() -> str:
    """Pick the active theme preference: session_state > cookie > 'system'.

    The profile-stored preference is applied to session_state by the auth
    flow once a user signs in (see app.auth._store_session). Until then we
    fall back to the per-browser cookie, then the system default.
    """
    pref = st.session_state.get(THEME_PREF_KEY)
    if pref in VALID_THEMES:
        return pref
    cookie_val = read_cookie_from_headers(THEME_COOKIE)
    if cookie_val in VALID_THEMES:
        st.session_state[THEME_PREF_KEY] = cookie_val
        return cookie_val
    # Dark-first default: the app renders dark out of the box, so default the
    # preference to dark_slate too -- keeps the toggle in sync on first load.
    return THEME_DARK_SLATE


# Global stylesheet now -- it consumes CSS vars but they have safe defaults
# (Streamlit's config.toml block sets the same palette via base/bg/text, so
# any unset var falls back to a sensible Neutral Slate dark). The real
# per-user palette CSS is injected AFTER session restore, below.
st.markdown(render_combined_css(), unsafe_allow_html=True)


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
# cookie. Streamlit Cloud's proxy strips the Cookie header before it reaches
# the WebSocket upgrade, so restore_session_from_cookie() falls back to the
# cookie_reader custom component which reads document.cookie client-side and
# sends the value back via Streamlit's component-value postMessage protocol.
# That triggers one extra rerun (component value arrives async) on first cold
# load; the script reruns with the value and restores the session.
restore_session_from_cookie()
session = get_session()
apply_session_to_client()

# Theme injection NOW -- the user's stored preference was loaded into
# session_state by _store_session above (if signed in). For signed-out
# users this picks the cookie or 'system'.
st.markdown(render_theme_css(_resolve_theme_pref()), unsafe_allow_html=True)

COLD_LOAD_GRACE_KEY = "_cold_load_grace_done"

if session:
    pages = [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True, url_path=""),
        st.Page("pages/practice.py", title="Practice", icon=":material/quiz:", url_path="practice"),
        st.Page("pages/timed_exam.py", title="Timed exam", icon=":material/timer:", url_path="timed_exam"),
        st.Page("pages/review.py", title="Review", icon=":material/replay:", url_path="review"),
        st.Page("pages/bookmarks.py", title="Bookmarks", icon=":material/bookmark:", url_path="bookmarks"),
        st.Page("pages/flashcards.py", title="Flashcards", icon=":material/style:", url_path="flashcards"),
        st.Page("pages/glossary.py", title="Glossary", icon=":material/menu_book:", url_path="glossary"),
        st.Page("pages/stats.py", title="Stats", icon=":material/insights:", url_path="stats"),
        st.Page("pages/account.py", title="Account", icon=":material/person:", url_path="account"),
        # URL-routable but hidden from the sidebar nav -- reached by clicking
        # a row on the Stats page's recent-sessions table.
        st.Page("pages/session_detail.py", title="Session detail", url_path="session"),
    ]
else:
    # Include the authenticated pages so URL routing resolves on deeplinks;
    # each page redirects to /login via in-page current_user() check. Visible
    # nav is hidden for unauth, so these don't appear in the sidebar.
    pages = [
        st.Page("pages/login.py", title="Sign in", icon=":material/login:", default=True, url_path=""),
        st.Page("pages/reset_password.py", title="Reset password", url_path="reset_password"),
        st.Page("pages/guest_practice.py", title="Practice as guest", url_path="guest_practice"),
        st.Page("pages/glossary.py", title="Glossary", url_path="glossary"),
        st.Page("pages/practice.py", title="Practice", url_path="practice"),
        st.Page("pages/timed_exam.py", title="Timed exam", url_path="timed_exam"),
        st.Page("pages/review.py", title="Review", url_path="review"),
        st.Page("pages/bookmarks.py", title="Bookmarks", url_path="bookmarks"),
        st.Page("pages/flashcards.py", title="Flashcards", url_path="flashcards"),
        st.Page("pages/stats.py", title="Stats", url_path="stats"),
        st.Page("pages/account.py", title="Account", url_path="account"),
        st.Page("pages/session_detail.py", title="Session detail", url_path="session"),
    ]

pg = st.navigation(pages, position="sidebar" if session else "hidden")

# Cold-load grace: when the URL is a deeplink to an auth-only page and we
# have no session yet, the cookie_reader component hasn't posted its value
# back on this first render. Render a placeholder and st.stop() AFTER nav
# was registered (so the URL is preserved) but BEFORE pg.run() (so the
# target page doesn't redirect to /login pre-emptively).
#
# Skip grace for pages that work fine without a session ("", glossary,
# guest_practice, reset_password). Guests browsing /glossary should see it
# immediately, not flash a Loading screen that the cookie_reader's null
# value won't always trigger a rerun out of.
GUEST_FRIENDLY_PATHS = {"", "glossary", "guest_practice", "reset_password"}

if (
    not session
    and not st.session_state.get(COLD_LOAD_GRACE_KEY)
    and pg.url_path not in GUEST_FRIENDLY_PATHS
):
    st.session_state[COLD_LOAD_GRACE_KEY] = True
    st.markdown(
        """
        <div style="display:flex;align-items:center;justify-content:center;height:60vh;">
          <div style="text-align:center;color:#6B7280;">
            <div style="font-size:1.05rem;margin-bottom:0.3rem;">Loading...</div>
            <div style="font-size:0.85rem;">Restoring your session</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Quick "Dark mode" toggle: appears in the sidebar bottom for auth users
# and in the page header for guests. Flips theme_preference between
# THEME_DARK_SLATE and THEME_LIGHT -- the full 4-option selector
# (System / Light / Slate / High Contrast) still lives on /account for
# users who want the deeper-contrast variant or to follow system theme.

_current_theme_pref = _resolve_theme_pref()


def _is_dark_pref(pref: str) -> bool:
    """Return True if a stored preference paints dark.

    "system" counts as dark because resolve_palette_name renders it as Dark
    Slate -- so the toggle reflects what the user actually sees.
    """
    return pref in (THEME_DARK_SLATE, THEME_DARK_HC, THEME_SYSTEM)


def _flip_dark(new_dark: bool, save_to_profile: bool, user_id: str | None) -> None:
    """Persist a quick-toggle flip: dark_slate when on, light when off."""
    new_pref = THEME_DARK_SLATE if new_dark else THEME_LIGHT
    st.session_state["theme_preference"] = new_pref
    st.session_state[_PENDING_THEME_WRITE_KEY] = new_pref
    if save_to_profile and user_id:
        try:
            set_theme_preference(user_id, new_pref)
        except Exception:  # noqa: BLE001 -- toggle should never block render
            pass


if not session:
    # Guest: toggle lives in the page header (sidebar nav is hidden for unauth).
    _, _toggle_col = st.columns([9, 2])
    with _toggle_col:
        _new_dark_guest = st.toggle(
            "Dark mode",
            value=_is_dark_pref(_current_theme_pref),
            key="dark_mode_toggle_guest",
        )
    if _new_dark_guest != _is_dark_pref(_current_theme_pref):
        _flip_dark(_new_dark_guest, save_to_profile=False, user_id=None)
        st.rerun()

# Sidebar contents for authenticated users: a compact dark stats panel + the
# signed-in label + sign-out. Lives here (not in each page) so it survives
# navigation. Stats queries are @st.cache_data(ttl=30) so the fetch is cheap.
if session:
    # initial_sidebar_state="expanded" on st.set_page_config only takes
    # effect on cold load. After login (a rerun, not a cold load), the
    # sidebar stays collapsed from the prior position="hidden" unauth
    # render. Poll for the expand button from the page DOM and click it
    # once per browser session. st.html with unsafe_allow_javascript=True
    # is required because st.markdown strips <script>; the modern
    # replacement for components.v1.html (deprecated 2026-06-01).
    st.html(
        """
        <script>
        (function () {
            const flag = '__awsomequizExpandClicked';
            const findClickable = () => {
                const candidates = [
                    '[data-testid="stExpandSidebarButton"] button',
                    '[data-testid="stExpandSidebarButton"]',
                    'button[data-testid="stExpandSidebarButton"]',
                    '[data-testid="stSidebarCollapsedControl"] button',
                    '[data-testid="collapsedControl"] button',
                ];
                for (const sel of candidates) {
                    const el = document.querySelector(sel);
                    if (el && (el.tagName === 'BUTTON' || el.querySelector('button') || el.click)) {
                        return el.tagName === 'BUTTON' ? el : (el.querySelector('button') || el);
                    }
                }
                return null;
            };
            const tryExpand = () => {
                try {
                    if (window[flag]) return true;
                    // Mobile: keep the sidebar collapsed by default; an open
                    // sidebar covers 60-70% of a phone screen and obscures
                    // the page content. Desktop / tablet keep the auto-open.
                    if (window.innerWidth < 768) {
                        window[flag] = true;
                        return true;
                    }
                    const sidebar = document.querySelector('[data-testid="stSidebar"]');
                    if (sidebar && sidebar.getAttribute('aria-expanded') === 'true') {
                        window[flag] = true;
                        return true;
                    }
                    const btn = findClickable();
                    if (btn) {
                        btn.click();
                        window[flag] = true;
                        return true;
                    }
                } catch (_) { return true; }
                return false;
            };
            if (!tryExpand()) {
                const t = setInterval(() => { if (tryExpand()) clearInterval(t); }, 150);
                setTimeout(() => clearInterval(t), 6000);
            }
        })();
        </script>
        """,
        unsafe_allow_javascript=True,
    )
    with st.sidebar:
        _render_sidebar_cert_picker()
        _render_sidebar_mini_stats(session)
        st.divider()
        u = session.get("user") or {}
        user_email = u.get("email") or "(unknown)"
        display = get_display_name(u.get("id") or "", user_email)
        st.caption(f"Signed in as **{display}**")
        if st.button("Sign out", width="stretch", key="sidebar_signout"):
            sign_out()
            st.rerun()
        # Quick dark-mode toggle. Goes between dark_slate and light; the
        # full 4-option (System / Light / Slate / High Contrast) lives on
        # /account. The handler also persists to the profile so the choice
        # follows across devices, same as the radio.
        st.divider()
        _new_dark_auth = st.toggle(
            "Dark mode",
            value=_is_dark_pref(_current_theme_pref),
            key="dark_mode_toggle_sidebar",
        )
        if _new_dark_auth != _is_dark_pref(_current_theme_pref):
            _flip_dark(_new_dark_auth, save_to_profile=True, user_id=u.get("id"))
            st.rerun()

pg.run()
