"""Supabase client factory. Cached so we don't reconnect on every rerun."""

from __future__ import annotations

import os

import streamlit as st
from supabase import Client, create_client
from supabase.client import ClientOptions


def _secret(name: str) -> str | None:
    """Pull a config value from env first, then st.secrets if it exists."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        return st.secrets[name]
    except (KeyError, FileNotFoundError):
        return None


@st.cache_resource
def get_supabase() -> Client:
    """Return a cached Supabase client (one per Streamlit process).

    Uses PKCE so OAuth + email-link flows return a `code` we can exchange
    rather than a URL fragment we'd need JavaScript to read.
    """
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_ANON_KEY")
    if not url or not key:
        st.error(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set. "
            "Copy `.env.example` to `.env` (Docker) or `.streamlit/secrets.toml.example` "
            "to `.streamlit/secrets.toml` (local), then `supabase status` to fill the keys."
        )
        st.stop()
    return create_client(url, key, options=ClientOptions(flow_type="pkce"))
