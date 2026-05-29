"""Free-practice page.

State flow:
  1. Summary in state -> render summary card (back to home / start another).
  2. No active session -> show resume CTA (if one exists in DB) or picker.
  3. Active session -> delegate to the shared runner component.
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.components.runner import render_runner, render_summary
from app.queries import (
    format_started_at,
    get_answered_question_ids,
    get_current_certification,
    list_domains,
)
from app.session import (
    abandon_session,
    get_active_practice_session,
    start_practice_session,
)

NAMESPACE = "practice"
SESSION_KEY = f"{NAMESPACE}_session"
INDEX_KEY = f"{NAMESPACE}_index"
SUMMARY_KEY = f"{NAMESPACE}_summary"


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()

st.title("Practice")

# 1. Summary (just completed)
if summary := st.session_state.get(SUMMARY_KEY):
    action = render_summary(summary, restart_label="Practice again")
    if action == "restart":
        st.session_state.pop(SUMMARY_KEY, None)
        st.rerun()
    st.stop()

# 2. Resume or picker
session = st.session_state.get(SESSION_KEY)
if session is None:
    existing = get_active_practice_session(user["id"])
    if existing:
        answered = len(get_answered_question_ids(existing["id"]))
        st.info(
            f"You have an unfinished session: "
            f"**{answered}/{existing['question_count']}** answered, "
            f"started {format_started_at(existing['started_at'])}."
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
        if c2.button("Abandon and start new"):
            abandon_session(existing["id"])
            st.rerun()
        st.stop()

if session is None:
    cert = get_current_certification()
    domains = list_domains(cert["id"])
    domain_labels = ["All"] + [d["name"] for d in domains]
    with st.form("practice_picker"):
        domain_choice = st.selectbox("Domain", options=domain_labels)
        count_choice = st.radio(
            "Number of questions",
            options=[10, 25, 50, "All"],
            horizontal=True,
        )
        order_choice = st.radio(
            "Order",
            options=["Sequential", "Random"],
            horizontal=True,
            index=0,
            help=(
                "Sequential: questions in their natural source order -- pick "
                "this to work through the whole set in order. "
                "Random: shuffled each session."
            ),
        )
        start_at = st.number_input(
            "Start at question #",
            min_value=1,
            value=1,
            step=1,
            help=(
                "Begin partway into the set instead of question 1 -- e.g. pick "
                "Sequential + 'All' and start at 210 to resume the bank there. "
                "You can also jump to any question mid-session from the sidebar."
            ),
        )
        start = st.form_submit_button(
            "Start practice", type="primary", width="stretch"
        )
    if start:
        domain_ids = (
            [d["id"] for d in domains if d["name"] == domain_choice]
            if domain_choice != "All"
            else None
        )
        count = None if count_choice == "All" else int(count_choice)
        shuffle = order_choice == "Random"
        try:
            new_session = start_practice_session(
                user["id"], cert["id"], count, domain_ids, shuffle=shuffle,
            )
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        st.session_state[SESSION_KEY] = new_session
        st.session_state[INDEX_KEY] = max(
            0, min(int(start_at) - 1, len(new_session["question_ids"]) - 1)
        )
        st.rerun()
    st.stop()

# 3. Active session -> runner (allow jumping directly to any question #)
render_runner(session, user, NAMESPACE, allow_jump=True)
