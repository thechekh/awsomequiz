"""Guest practice page.

A trimmed-down practice mode for unauthenticated visitors. Picks N random
questions from public.questions (anon-readable since migration 0006) and
runs a forward-only flow entirely in st.session_state. No DB writes,
no exam_sessions row, no user_answers row. Closing the tab loses
everything; this is intentional -- to keep progress, the visitor signs up.
"""

from __future__ import annotations

import streamlit as st

from app.queries import get_clf_certification, get_question_with_options, pick_question_ids

QUEUE_KEY = "guest_queue"
INDEX_KEY = "guest_index"
ANSWERS_KEY = "guest_answers"
SUMMARY_KEY = "guest_summary"

DEFAULT_COUNT = 10


def _clear_guest_state() -> None:
    for k in (QUEUE_KEY, INDEX_KEY, ANSWERS_KEY, SUMMARY_KEY):
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if k.startswith("guest_radio_") or k.startswith("guest_cb_"):
            st.session_state.pop(k, None)


def _start_guest_session(count: int) -> None:
    cert = get_clf_certification()
    if not cert:
        st.error("Question bank not seeded.")
        return
    ids = pick_question_ids(cert["id"], count)
    if not ids:
        st.error("No questions available.")
        return
    st.session_state[QUEUE_KEY] = ids
    st.session_state[INDEX_KEY] = 0
    st.session_state[ANSWERS_KEY] = {}
    st.session_state.pop(SUMMARY_KEY, None)
    st.rerun()


st.title("Practice (guest)")
st.caption(
    "Try the question runner without signing in. Progress isn't saved -- "
    "[sign in or create a free account](./) to keep your stats, streaks and bookmarks."
)
st.divider()

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if summary := st.session_state.get(SUMMARY_KEY):
    pct = summary["score_pct"]
    if pct >= 70:
        st.success(
            f"Session complete: **{pct}%** ({summary['correct']}/{summary['total']}) -- passed"
        )
    else:
        st.error(
            f"Session complete: **{pct}%** ({summary['correct']}/{summary['total']}) -- "
            f"below 70% pass threshold"
        )
    st.caption(
        "Sign in to save sessions, track streaks, build a missed-questions queue, "
        "and unlock timed exams + flashcards."
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Practice again", type="primary"):
        _clear_guest_state()
        st.rerun()
    if c2.button("Sign in"):
        st.switch_page("pages/login.py")
    if c3.button("Quit"):
        _clear_guest_state()
        st.switch_page("pages/login.py")
    st.stop()

# ---------------------------------------------------------------------------
# Picker
# ---------------------------------------------------------------------------

queue = st.session_state.get(QUEUE_KEY)
if queue is None:
    with st.form("guest_picker"):
        count_choice = st.radio(
            "Number of questions",
            options=[10, 25, 50],
            horizontal=True,
            index=0,
        )
        start = st.form_submit_button(
            "Start practice", type="primary", use_container_width=True
        )
    if st.button("Or sign in to unlock all modes", key="guest_picker_signin"):
        st.switch_page("pages/login.py")
    if start:
        _start_guest_session(int(count_choice))
    st.stop()

# ---------------------------------------------------------------------------
# Question runner (forward-only, all in session_state)
# ---------------------------------------------------------------------------

total = len(queue)
index = st.session_state.get(INDEX_KEY, 0)
answers = st.session_state.setdefault(ANSWERS_KEY, {})

with st.sidebar:
    st.divider()
    st.metric("Question", f"{min(index + 1, total)} / {total}")
    st.caption("Guest session -- not saved.")
    if st.button("Quit", use_container_width=True, key="guest_quit"):
        _clear_guest_state()
        st.switch_page("pages/login.py")

# End of queue -> compute summary
if index >= total:
    correct = sum(1 for a in answers.values() if a["is_correct"])
    score_pct = round(correct / total * 100, 1) if total else 0.0
    st.session_state[SUMMARY_KEY] = {
        "total": total,
        "correct": correct,
        "score_pct": score_pct,
    }
    st.rerun()

qid = queue[index]
question = get_question_with_options(qid)
opt_by_id = {o["id"]: o for o in question["options"]}
correct_ids = [o["id"] for o in question["options"] if o["is_correct"]]
prior = answers.get(qid)

st.subheader(f"Question {index + 1}")
st.markdown(question["stem"])

if prior is None:
    if question["type"] == "single":
        chosen = st.radio(
            "Choose one",
            options=[o["id"] for o in question["options"]],
            format_func=lambda oid: f"{opt_by_id[oid]['label']}. {opt_by_id[oid]['text']}",
            key=f"guest_radio_{qid}",
            index=None,
        )
        if st.button("Submit", type="primary", key=f"guest_submit_{qid}", disabled=chosen is None):
            answers[qid] = {
                "selected_option_ids": [chosen],
                "is_correct": sorted([chosen]) == sorted(correct_ids),
            }
            st.rerun()
    else:
        needed = len(correct_ids)
        st.caption(f"Select exactly {needed} options.")
        selected: list[str] = []
        for o in question["options"]:
            if st.checkbox(f"{o['label']}. {o['text']}", key=f"guest_cb_{qid}_{o['id']}"):
                selected.append(o["id"])
        if st.button(
            "Submit",
            type="primary",
            key=f"guest_submit_{qid}",
            disabled=len(selected) != needed,
        ):
            answers[qid] = {
                "selected_option_ids": selected,
                "is_correct": sorted(selected) == sorted(correct_ids),
            }
            st.rerun()
else:
    selected_ids = prior["selected_option_ids"]
    if prior["is_correct"]:
        st.success("Correct!")
    else:
        st.error("Incorrect.")

    st.divider()
    for o in question["options"]:
        was_selected = o["id"] in selected_ids
        is_right = o["is_correct"]
        marker = "✅" if is_right else "❌"
        you = "  (your answer)" if was_selected else ""
        line = f"{marker} **{o['label']}. {o['text']}**{you}"
        if is_right and was_selected:
            st.success(line)
        elif is_right:
            st.success(line)
        elif was_selected:
            st.error(line)
        else:
            st.write(line)
        if o.get("explanation_detailed"):
            st.markdown(o["explanation_detailed"])
        if o.get("related_context"):
            st.markdown(f"*Related:* {o['related_context']}")
        st.write("")

    next_label = "Finish session" if index + 1 == total else "Next question"
    if st.button(next_label, type="primary", key=f"guest_next_{qid}", use_container_width=True):
        st.session_state[INDEX_KEY] = index + 1
        st.rerun()
