"""Supabase auth helpers.

Session lifecycle: we hold a dict copy of the Supabase Session in
`st.session_state["supabase_session"]` (Streamlit-native, survives reruns) and
push it onto the cached Supabase client via `apply_session_to_client()` so RLS
sees the user. The supabase-py client auto-refreshes near expiry; we also do a
defensive refresh in `get_session()` because Streamlit's reruns can leave the
client out of sync.
"""

from __future__ import annotations

import os
import time
from typing import Literal

import streamlit as st

from app.db import get_supabase

SESSION_KEY = "supabase_session"
COOKIE_NAME = "awsomequiz_rt"
COOKIE_MAX_AGE_DAYS = 30
DARK_MODE_KEY = "dark_mode"  # Shared so pages can render theme-aware UI bits.
OtpType = Literal["signup", "recovery", "email_change", "invite", "magiclink"]

# ---------------------------------------------------------------------------
# Browser-cookie persistence for the Supabase refresh token (login survives
# page reloads). The actual document.cookie write happens in streamlit_app.py
# at the top of the script via inline-JS components.html (CookieManager's
# React chunk aborts on Streamlit Cloud). The helpers below just queue the
# request via session_state. See _save_refresh_cookie for why.
# ---------------------------------------------------------------------------

PENDING_SAVE_KEY = "_pending_refresh_cookie_save"
PENDING_DELETE_KEY = "_pending_refresh_cookie_delete"


def _save_refresh_cookie(refresh_token: str) -> None:
    """Queue a refresh-token cookie write for streamlit_app.py to perform.

    Direct cm.set() / components.html(...) calls from this module are at
    unstable DOM positions (login.py form callbacks, page bodies) -- the
    immediately-following st.rerun() tears down those positions before
    the cookie iframe can process the write, so the cookie never lands.
    streamlit_app.py runs from the top on every rerun, so any cookie
    operation rendered there has a stable DOM position and survives the
    transition from login -> home.
    """
    if not refresh_token:
        return
    st.session_state[PENDING_SAVE_KEY] = refresh_token
    # If a delete was queued earlier in the same run, the save wins.
    st.session_state.pop(PENDING_DELETE_KEY, None)


def _read_refresh_cookie() -> str | None:
    """Read the refresh token from the HTTP request headers.

    Server-side and synchronous. Doesn't depend on the CookieManager iframe
    having loaded, which solves the cold-load race where the iframe hadn't
    sent cookies back to Python yet on the first script run after a refresh.
    """
    try:
        headers = st.context.headers
    except Exception:  # noqa: BLE001 - st.context may not be ready in some test contexts
        return None
    cookie_header = headers.get("Cookie") or headers.get("cookie") or ""
    for chunk in cookie_header.split(";"):
        chunk = chunk.strip()
        if chunk.startswith(f"{COOKIE_NAME}="):
            from urllib.parse import unquote
            return unquote(chunk[len(COOKIE_NAME) + 1:])
    return None


def _delete_refresh_cookie() -> None:
    """Queue a refresh-token cookie deletion for streamlit_app.py to perform.

    Same reasoning as _save_refresh_cookie: page-callback DOM positions
    are torn down before the cookie operation can complete; queue and
    let the stable top of streamlit_app.py do the work.
    """
    st.session_state[PENDING_DELETE_KEY] = True
    st.session_state.pop(PENDING_SAVE_KEY, None)


def restore_session_from_cookie() -> dict | None:
    """If no session in st.session_state but a refresh-token cookie exists,
    exchange it for a fresh session via Supabase. Called from streamlit_app.py
    on every cold start.

    Synchronous: _read_refresh_cookie now reads from st.context.headers, so
    no CookieManager-iframe-loading race to manage.
    """
    if st.session_state.get(SESSION_KEY):
        return st.session_state[SESSION_KEY]

    refresh_token = _read_refresh_cookie()
    if not refresh_token:
        return None

    try:
        client = get_supabase()
        resp = client.auth.refresh_session(refresh_token)
        if resp.session:
            return _store_session(resp.session)
    except Exception:  # noqa: BLE001 - bad / expired token
        _delete_refresh_cookie()
    return None


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _session_to_dict(session) -> dict:
    """Convert a supabase-py Session model to a plain dict for st.session_state."""
    user = session.user
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
        "expires_in": session.expires_in,
        "token_type": session.token_type,
        "user": {
            "id": user.id,
            "email": user.email,
            "email_confirmed_at": str(user.email_confirmed_at) if user.email_confirmed_at else None,
            "created_at": str(user.created_at) if user.created_at else None,
        } if user else None,
    }


def _store_session(session) -> dict:
    d = _session_to_dict(session)
    st.session_state[SESSION_KEY] = d
    # Persist the refresh token in a cookie so the user stays signed in after
    # closing the tab / reloading. Access tokens are short-lived; we only
    # store the long-lived refresh token.
    _save_refresh_cookie(d.get("refresh_token") or "")
    return d


def _clear_session() -> None:
    st.session_state.pop(SESSION_KEY, None)
    _delete_refresh_cookie()


def get_session() -> dict | None:
    """Return the active session, refreshing if it expires within 60 s. None if signed out."""
    session = st.session_state.get(SESSION_KEY)
    if not session:
        return None
    expires_at = session.get("expires_at") or 0
    if expires_at - time.time() < 60:
        try:
            client = get_supabase()
            resp = client.auth.refresh_session(session["refresh_token"])
            if resp.session:
                session = _store_session(resp.session)
            else:
                _clear_session()
                return None
        except Exception:  # noqa: BLE001 - refresh can fail for many reasons; treat all as signed-out
            _clear_session()
            return None
    return session


def current_user() -> dict | None:
    """Convenience: return the user dict of the active session, or None."""
    session = get_session()
    return session["user"] if session else None


def apply_session_to_client() -> None:
    """Push the stored access+refresh tokens onto the cached Supabase client.

    Streamlit reruns recreate the page module but reuse the cached client, so
    this must be called on every rerun before any query that needs RLS.
    """
    session = st.session_state.get(SESSION_KEY)
    if not session:
        return
    client = get_supabase()
    client.auth.set_session(session["access_token"], session["refresh_token"])


# ---------------------------------------------------------------------------
# Email / password flows
# ---------------------------------------------------------------------------


def sign_up(email: str, password: str) -> dict:
    """Register a new user. Returns dict with `needs_confirmation` flag if email
    verification is required (per Supabase auth config).
    """
    client = get_supabase()
    resp = client.auth.sign_up({
        "email": email,
        "password": password,
        "options": {"email_redirect_to": site_url()},
    })
    if resp.session:
        return {"needs_confirmation": False, **_store_session(resp.session)}
    # No session means Supabase requires verification before signin.
    return {
        "needs_confirmation": True,
        "user": {"email": resp.user.email if resp.user else email},
    }


def sign_in(email: str, password: str) -> dict:
    client = get_supabase()
    resp = client.auth.sign_in_with_password({"email": email, "password": password})
    if not resp.session:
        raise RuntimeError("Sign-in succeeded but no session returned (Supabase bug?).")
    return _store_session(resp.session)


def sign_out() -> None:
    """Best-effort sign out: tell Supabase, then clear local session regardless."""
    try:
        client = get_supabase()
        client.auth.sign_out()
    except Exception:  # noqa: BLE001 - network failure should not block local signout
        pass
    _clear_session()


def reset_password_request(email: str) -> None:
    """Trigger the password-reset email. Link in the email lands on /reset_password."""
    client = get_supabase()
    client.auth.reset_password_for_email(
        email,
        {"redirect_to": f"{site_url()}/reset_password"},
    )


def update_password(new_password: str) -> dict:
    """Change the currently signed-in user's password. Requires a live session."""
    client = get_supabase()
    apply_session_to_client()
    resp = client.auth.update_user({"password": new_password})
    if resp.user:
        # Pick up any rotated tokens returned by Supabase.
        live = client.auth.get_session()
        if live:
            return _store_session(live)
    return st.session_state.get(SESSION_KEY, {})


# ---------------------------------------------------------------------------
# Email-link verification (signup confirmation + password recovery)
# ---------------------------------------------------------------------------


def verify_otp(token_hash: str, otp_type: OtpType) -> dict | None:
    """Verify an email-link token (signup, recovery, magic-link, etc.).

    Returns the new session dict if verification yielded one (recovery,
    magiclink), else None (signup-only confirmation produces no session by
    default — user still needs to sign in).
    """
    client = get_supabase()
    resp = client.auth.verify_otp({"token_hash": token_hash, "type": otp_type})
    if resp.session:
        return _store_session(resp.session)
    return None


# ---------------------------------------------------------------------------
# OAuth (GitHub)
# ---------------------------------------------------------------------------


def get_github_oauth_url() -> str | None:
    """Return the URL to redirect the user to for GitHub OAuth, or None on failure.

    Note: supabase-py.sign_in_with_oauth returns a URL regardless of whether
    the provider is actually enabled server-side -- it just constructs the
    request URL. So a non-None return here doesn't *prove* GitHub is configured;
    the actual validation happens when the user clicks through and Supabase
    rejects unsupported providers.
    """
    client = get_supabase()
    try:
        resp = client.auth.sign_in_with_oauth({
            "provider": "github",
            "options": {
                "redirect_to": site_url(),
                "skip_browser_redirect": True,
            },
        })
        return getattr(resp, "url", None)
    except Exception:  # noqa: BLE001 - swallow client errors so the page can hide the button
        return None


def exchange_code(code: str) -> dict | None:
    """Exchange a PKCE auth code (from OAuth or magic-link callback) for a session."""
    client = get_supabase()
    try:
        resp = client.auth.exchange_code_for_session({"auth_code": code})
        if resp.session:
            return _store_session(resp.session)
    except Exception:  # noqa: BLE001 - bad / expired code; let caller show a clean error
        return None
    return None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def site_url() -> str:
    """The public URL of the running Streamlit app.

    Defaults to http://localhost:8501 for local dev. Override via
    APP_SITE_URL env var or [APP_SITE_URL] in st.secrets when deploying.
    """
    val = os.environ.get("APP_SITE_URL")
    if val:
        return val.rstrip("/")
    try:
        return str(st.secrets["APP_SITE_URL"]).rstrip("/")
    except (KeyError, FileNotFoundError):
        return "http://localhost:8501"
