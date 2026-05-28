"""Review page: weak-areas + missed-questions practice modes.

Two tabs. Each tab picks questions via a mode-specific selector and then drops
into the shared runner. Only one weak/missed session can be in flight at a
time (enforced by the picker, which offers Resume / Abandon if one exists).
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.components.runner import render_runner, render_summary
from app.queries import (
    get_answered_question_ids,
    get_current_certification,
    pick_missed_question_ids,
    pick_weak_area_question_ids,
)
from app.session import (
    abandon_session,
    get_active_review_session,
    start_missed_session,
    start_weak_areas_session,
)

NAMESPACE = "review"
SESSION_KEY = f"{NAMESPACE}_session"
INDEX_KEY = f"{NAMESPACE}_index"
SUMMARY_KEY = f"{NAMESPACE}_summary"

WEAK_THRESHOLD_PCT = 70
WEAK_MIN_ATTEMPTS = 3


def _count_options(available: int) -> list[int | str]:
    """Filter the standard 10/25/50/All choices to what's actually available."""
    sizes: list[int | str] = [n for n in (10, 25, 50) if n <= available]
    sizes.append("All")
    return sizes


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()
cert = get_current_certification()

st.title("Review")

# 1. Summary
if summary := st.session_state.get(SUMMARY_KEY):
    action = render_summary(summary, restart_label="Review more")
    if action == "restart":
        st.session_state.pop(SUMMARY_KEY, None)
        st.rerun()
    st.stop()

# 2. Active session (delegate to runner)
session = st.session_state.get(SESSION_KEY)
if session is not None:
    render_runner(session, user, NAMESPACE)
    st.stop()

# 3. Resume incomplete weak/missed session if one exists
existing = get_active_review_session(user["id"])
if existing:
    answered = len(get_answered_question_ids(existing["id"]))
    mode_label = existing["mode"].replace("_", " ").title()
    st.info(
        f"Unfinished **{mode_label}** session: "
        f"**{answered}/{existing['question_count']}** answered."
    )
    c1, c2 = st.columns(2)
    if c1.button("Resume", type="primary"):
        st.session_state[SESSION_KEY] = existing
        answered_ids = get_answered_question_ids(existing["id"])
        for i, qid in enumerate(existing["question_ids"]):
            if qid not in answered_ids:
                st.session_state[INDEX_KEY] = i
                break
        else:
            st.session_state[INDEX_KEY] = len(existing["question_ids"])
        st.rerun()
    if c2.button("Abandon and pick a different mode"):
        abandon_session(existing["id"])
        st.rerun()
    st.stop()

# 4. Mode picker (tabs)
weak_tab, missed_tab = st.tabs(["Weak areas", "Missed questions"])

with weak_tab:
    st.caption(
        f"Questions where your accuracy is **below {WEAK_THRESHOLD_PCT}%** "
        f"after at least {WEAK_MIN_ATTEMPTS} attempts, plus questions you've "
        f"never seen. Random sample each time."
    )
    available = len(pick_weak_area_question_ids(
        user["id"], cert["id"], None, WEAK_THRESHOLD_PCT, WEAK_MIN_ATTEMPTS,
    ))
    if available == 0:
        st.warning(
            "No weak-area questions yet. Run a few practice or timed sessions first."
        )
    else:
        st.caption(f"**{available}** questions eligible.")
        with st.form("weak_picker"):
            count_choice = st.radio(
                "Number of questions",
                options=_count_options(available),
                horizontal=True,
                key="weak_count",
            )
            start = st.form_submit_button(
                "Start weak-areas review", type="primary", width="stretch"
            )
        if start:
            count = None if count_choice == "All" else int(count_choice)
            try:
                new = start_weak_areas_session(
                    user["id"], cert["id"], count, WEAK_THRESHOLD_PCT, WEAK_MIN_ATTEMPTS,
                )
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            st.session_state[SESSION_KEY] = new
            st.session_state[INDEX_KEY] = 0
            st.rerun()

with missed_tab:
    st.caption(
        "Questions you've gotten wrong in past sessions (practice or timed). "
        "Random sample each time."
    )
    available = len(pick_missed_question_ids(user["id"], cert["id"], None))
    if available == 0:
        st.warning(
            "No missed questions yet. Either you're flawless, or you haven't "
            "answered any yet -- try a practice session first."
        )
    else:
        st.caption(f"**{available}** questions you've gotten wrong.")
        with st.form("missed_picker"):
            count_choice = st.radio(
                "Number of questions",
                options=_count_options(available),
                horizontal=True,
                key="missed_count",
            )
            start = st.form_submit_button(
                "Start missed review", type="primary", width="stretch"
            )
        if start:
            count = None if count_choice == "All" else int(count_choice)
            try:
                new = start_missed_session(user["id"], cert["id"], count)
            except ValueError as exc:
                st.error(str(exc))
                st.stop()
            st.session_state[SESSION_KEY] = new
            st.session_state[INDEX_KEY] = 0
            st.rerun()
