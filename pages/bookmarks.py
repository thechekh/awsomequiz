"""Bookmarks page: manage saved questions + practice them.

Top: a "Practice all bookmarks" button that drops into the shared runner.
Below: the list of bookmarks with a Remove button on each row.

Bookmarked practice sessions live on this page (separate state namespace from
the review modes so a user can have one of each in flight if they really want).
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.components.runner import render_runner, render_summary
from app.queries import (
    delete_bookmark,
    format_started_at,
    get_clf_certification,
    list_bookmarks,
)
from app.session import (
    abandon_session,
    get_active_bookmarked_session,
    start_bookmarked_session,
)

NAMESPACE = "bookmarks"
SESSION_KEY = f"{NAMESPACE}_session"
INDEX_KEY = f"{NAMESPACE}_index"
SUMMARY_KEY = f"{NAMESPACE}_summary"

PREVIEW_CHARS = 140


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()
cert = get_clf_certification()

st.title("Bookmarks")

# 1. Summary (just completed)
if summary := st.session_state.get(SUMMARY_KEY):
    action = render_summary(summary, restart_label="Practice bookmarks again")
    if action == "restart":
        st.session_state.pop(SUMMARY_KEY, None)
        st.rerun()
    st.stop()

# 2. Active session -> runner
session = st.session_state.get(SESSION_KEY)
if session is not None:
    render_runner(session, user, NAMESPACE)
    st.stop()

# 3. Resume incomplete bookmarked session if one exists
existing = get_active_bookmarked_session(user["id"])
if existing:
    st.info(
        f"Unfinished **bookmarked** session: "
        f"started {format_started_at(existing['started_at'])}."
    )
    c1, c2 = st.columns(2)
    if c1.button("Resume", type="primary"):
        st.session_state[SESSION_KEY] = existing
        st.session_state[INDEX_KEY] = 0
        st.rerun()
    if c2.button("Abandon"):
        abandon_session(existing["id"])
        st.rerun()
    st.divider()

# 4. List + manage
bookmarks = list_bookmarks(user["id"], cert["id"])

if not bookmarks:
    st.info(
        "You haven't bookmarked any questions yet. Click the **Bookmark** "
        "button on any question to save it here."
    )
    st.stop()

st.caption(f"**{len(bookmarks)}** bookmarked.")
if st.button(
    "Practice all bookmarks",
    type="primary",
    use_container_width=False,
    disabled=len(bookmarks) == 0,
):
    try:
        new = start_bookmarked_session(user["id"], cert["id"], None)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    st.session_state[SESSION_KEY] = new
    st.session_state[INDEX_KEY] = 0
    st.rerun()

st.divider()

for bm in bookmarks:
    stem_preview = bm["stem"][:PREVIEW_CHARS]
    if len(bm["stem"]) > PREVIEW_CHARS:
        stem_preview += "..."
    col_text, col_btn = st.columns([8, 1])
    with col_text:
        st.markdown(stem_preview)
        st.caption(f"Bookmarked {bm['created_at']}")
    with col_btn:
        if st.button("Remove", key=f"rm_{bm['question_id']}"):
            delete_bookmark(user["id"], bm["question_id"])
            st.rerun()
    st.divider()
