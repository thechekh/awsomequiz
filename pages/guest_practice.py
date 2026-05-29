"""Guest practice page.

A trimmed-down practice mode for unauthenticated visitors. Picks N random
questions from public.questions (anon-readable since migration 0006) and
runs a forward-only flow entirely in st.session_state. No DB writes,
no exam_sessions row, no user_answers row. Closing the tab loses
everything; this is intentional -- to keep progress, the visitor signs up.
"""

from __future__ import annotations

import streamlit as st

from app.queries import (
    get_current_certification,
    get_question_with_options,
    list_certifications_with_questions,
    pick_question_ids,
    set_current_certification,
    summarize_answers_by_domain,
)

QUEUE_KEY = "guest_queue"
INDEX_KEY = "guest_index"
ANSWERS_KEY = "guest_answers"
SUMMARY_KEY = "guest_summary"


def _clear_guest_state() -> None:
    for k in (QUEUE_KEY, INDEX_KEY, ANSWERS_KEY, SUMMARY_KEY):
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if k.startswith("guest_radio_") or k.startswith("guest_cb_"):
            st.session_state.pop(k, None)


def _start_guest_session() -> None:
    """Start a guest session with ALL active questions in random order."""
    cert = get_current_certification()
    if not cert:
        st.error("Question bank not seeded.")
        return
    ids = pick_question_ids(cert["id"], count=None)  # all questions, shuffled
    if not ids:
        st.error("No questions available.")
        return
    st.session_state[QUEUE_KEY] = ids
    st.session_state[INDEX_KEY] = 0
    st.session_state[ANSWERS_KEY] = {}
    st.session_state.pop(SUMMARY_KEY, None)
    st.rerun()


def _finish_guest_session() -> None:
    """End now and build the summary from answered questions only.

    Computes total + per-category (domain) accuracy via
    summarize_answers_by_domain so the visitor sees where they're strong/weak.
    Questions not yet answered (including the current one) are excluded from the
    denominator -- "end on the current question" means count what's done so far.
    """
    answers = st.session_state.get(ANSWERS_KEY, {})
    cert = get_current_certification()
    if cert and answers:
        summary = summarize_answers_by_domain(cert["id"], answers)
    else:
        total = len(answers)
        correct = sum(1 for a in answers.values() if a.get("is_correct"))
        summary = {
            "total": total,
            "correct": correct,
            "score_pct": round(correct / total * 100, 1) if total else 0.0,
            "by_domain": [],
        }
    st.session_state[SUMMARY_KEY] = summary
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
    # Per-category (domain) accuracy breakdown.
    by_domain = summary.get("by_domain") or []
    if by_domain:
        st.markdown("#### Accuracy by category")
        for d in by_domain:
            st.markdown(
                f"**{d['name']}** — {d['accuracy_pct']}% "
                f"({d['correct']}/{d['total']} correct)"
            )
            st.progress(min(1.0, d["accuracy_pct"] / 100))
    elif summary.get("total"):
        st.caption("Per-category breakdown isn't available for this question set.")

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
# Certification picker (shown ONLY before the session has started). Guests
# pick their exam here rather than on Login so the Login page stays focused
# on auth. The choice writes through to session_state via
# set_current_certification; profile persistence kicks in only on sign-in.
# ---------------------------------------------------------------------------

queue = st.session_state.get(QUEUE_KEY)
if queue is None:
    available = list_certifications_with_questions()
    if not available:
        st.error("No certifications have a question bank loaded yet.")
        st.stop()
    current = get_current_certification()
    current_code = current["code"] if current else available[0]["code"]
    st.markdown("**Which exam do you want to practice?**")
    if len(available) == 1:
        st.caption(f"Practicing: **{available[0]['code']} — {available[0]['name']}**")
    else:
        chosen = st.selectbox(
            "Certification",
            options=[c["code"] for c in available],
            format_func=lambda code: f"{code} — {next(c['name'] for c in available if c['code'] == code)}",
            index=next((i for i, c in enumerate(available) if c["code"] == current_code), 0),
            key="guest_cert_picker",
            label_visibility="collapsed",
        )
        if chosen != current_code:
            set_current_certification(chosen)
            st.rerun()
    if st.button("Start practice", type="primary", width="stretch"):
        _start_guest_session()
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
    answered_count = len(answers)
    if answered_count and st.button(
        "End session & see results",
        type="primary",
        width="stretch",
        key="guest_end",
        help=f"Finish now and score the {answered_count} question(s) you've answered.",
    ):
        _finish_guest_session()
    if st.button("Quit", width="stretch", key="guest_quit"):
        _clear_guest_state()
        st.switch_page("pages/login.py")

# End of queue -> compute summary (with per-category breakdown)
if index >= total:
    _finish_guest_session()

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
        tag = '<span class="opt-tag">(your answer)</span>' if was_selected else ""
        row_class = "opt-row"
        if is_right:
            row_class += " correct"
        elif was_selected:
            row_class += " wrong"
        st.markdown(
            f'<div class="{row_class}">{marker} <b>{o["label"]}. {o["text"]}</b>{tag}</div>',
            unsafe_allow_html=True,
        )
        if o.get("explanation_detailed"):
            st.markdown(
                f'<div class="opt-explanation">{o["explanation_detailed"]}</div>',
                unsafe_allow_html=True,
            )
        if o.get("related_context"):
            st.markdown(
                f'<div class="opt-related">Related: {o["related_context"]}</div>',
                unsafe_allow_html=True,
            )

    next_label = "Finish session" if index + 1 == total else "Next question"
    if st.button(next_label, type="primary", key=f"guest_next_{qid}", width="stretch"):
        st.session_state[INDEX_KEY] = index + 1
        st.rerun()
