"""Supabase client factories.

Two deliberately separate clients:

* ``get_public_supabase()`` -- ONE process-wide anon client (``@st.cache_resource``)
  whose auth is **never** mutated. Used for world-readable reference reads
  (certifications, domains, questions, options). Its Authorization header stays
  the long-lived anon key, so these reads can't fail with ``PGRST303`` and never
  carry a user identity.

* ``get_supabase()`` -- a **per-browser-session** client held in
  ``st.session_state``. It wears *this* user's access token (applied by
  ``app.auth``) so RLS sees the right ``auth.uid()``, and is isolated from other
  visitors' sessions, so one user's token can't bleed into another's queries.
  When signed out it falls back to the anon key.

Why the split: the previous design used a single ``@st.cache_resource`` client
shared across every browser session in the server process AND called
``set_session()`` on it per request. A logged-in user's short-lived token would
linger on that shared client and later surface as ``JWT expired`` (PGRST303) for
guests / other users on the next cache-miss round-trip -- and worse, a query
could run under the wrong user's identity under concurrency. Separating a
never-mutated anon read-client from per-session authed clients fixes both.
"""

from __future__ import annotations

import os

import streamlit as st
from supabase import Client, create_client
from supabase.client import ClientOptions

# session_state key for the per-browser-session authed client.
_SESSION_CLIENT_KEY = "_sb_session_client"


def _secret(name: str) -> str | None:
    """Pull a config value from env first, then st.secrets if it exists."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError):
        return None


def _config() -> tuple[str, str]:
    """Return (url, anon_key) or stop the app with a setup hint if unset."""
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set. "
            "Copy `.env.example` to `.env` (Docker) or `.streamlit/secrets.toml.example` "
            "to `.streamlit/secrets.toml` (local), then `supabase status` to fill the keys."
        )
        st.stop()
    return url, key


def _new_client() -> Client:
    """Build a fresh client.

    PKCE so OAuth + email-link flows return a `code` we can exchange rather than
    a URL fragment. ``auto_refresh_token`` is off on purpose: in Streamlit we
    refresh deterministically in ``app.auth.get_session()`` on each rerun, and a
    per-session background refresh timer would otherwise accumulate one thread
    per visitor and keep the client alive past session cleanup.
    """
    url, key = _config()
    return create_client(
        url,
        key,
        options=ClientOptions(flow_type="pkce", auto_refresh_token=False),
    )


@st.cache_resource
def get_public_supabase() -> Client:
    """Shared anon client for world-readable reference reads. Never mutate its auth."""
    return _new_client()


def get_supabase() -> Client:
    """Return this browser session's client (carries the user's token, or anon).

    Stored in ``st.session_state`` so it's created once per session and reused
    across reruns -- honouring the "don't reconnect per rerun" constraint --
    while staying isolated from other users' sessions. ``app.auth`` applies the
    access token to it (and resets it to anon on sign-out).
    """
    client = st.session_state.get(_SESSION_CLIENT_KEY)
    if client is None:
        client = _new_client()
        st.session_state[_SESSION_CLIENT_KEY] = client
    return client


def reset_client_to_anon(client: Client) -> None:
    """Reset a client's PostgREST bearer back to the anon key.

    Defensive: ensures a no-session render can't keep sending a user token that
    was applied earlier in the same browser session (which would expire and
    raise PGRST303, or read under the wrong identity).
    """
    _, key = _config()
    try:
        client.postgrest.auth(key)
    except Exception:  # noqa: BLE001 -- never block render on a header reset
        pass


def drop_session_client() -> None:
    """Forget this session's client so the next ``get_supabase()`` builds a clean
    anon one. Called on sign-out / session clear."""
    st.session_state.pop(_SESSION_CLIENT_KEY, None)
