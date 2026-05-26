"""Per-question runner shared across practice / weak-areas / missed / bookmarked modes.

State convention -- the caller passes a `namespace` string and the runner derives:
    f"{namespace}_session"  -> the active session dict
    f"{namespace}_index"    -> current question index
    f"{namespace}_summary"  -> set when the session completes

The caller is responsible for:
- Showing the picker UI and writing the session dict into session_state.
- Rendering the summary screen after the runner sets the summary key.
- Routing -- this component only renders the in-session UI (sidebar + question).
"""

from __future__ import annotations

import time

import streamlit as st

from app.queries import (
    get_question_with_options,
    get_user_answer,
    is_bookmarked,
    toggle_bookmark,
)
from app.session import abandon_session, complete_session, record_answer


def _clear_runner_state(namespace: str) -> None:
    """Drop the runner's session/index keys + any widget keys it created."""
    drop_keys = (
        f"{namespace}_session",
        f"{namespace}_index",
    )
    for k in drop_keys:
        st.session_state.pop(k, None)
    for k in list(st.session_state.keys()):
        if k.startswith("runner_") or k.startswith("qst_"):
            st.session_state.pop(k, None)


def render_runner(session: dict, user: dict, namespace: str) -> None:
    """Render the in-session UI. Writes summary to f'{namespace}_summary' when done."""
    session_key = f"{namespace}_session"
    index_key = f"{namespace}_index"
    summary_key = f"{namespace}_summary"

    question_ids = session["question_ids"]
    total = len(question_ids)
    index = st.session_state.get(index_key, 0)

    with st.sidebar:
        st.divider()
        st.metric("Question", f"{min(index + 1, total)} / {total}")
        if st.button("Quit session", use_container_width=True, key=f"runner_quit_{namespace}"):
            abandon_session(session["id"])
            _clear_runner_state(namespace)
            st.rerun()

    if index >= total:
        summary = complete_session(session["id"])
        _clear_runner_state(namespace)
        st.session_state[summary_key] = summary
        st.rerun()

    qid = question_ids[index]
    question = get_question_with_options(qid)
    opt_by_id = {o["id"]: o for o in question["options"]}
    correct_ids = [o["id"] for o in question["options"] if o["is_correct"]]
    prior = get_user_answer(session["id"], qid)

    hcol, bcol = st.columns([7, 1])
    hcol.subheader(f"Question {index + 1}")

    bookmarked = is_bookmarked(user["id"], qid)
    bm_label = "Bookmarked" if bookmarked else "Bookmark"
    if bcol.button(bm_label, key=f"runner_bm_{qid}", use_container_width=True):
        toggle_bookmark(user["id"], qid)
        st.rerun()

    st.markdown(question["stem"])

    if prior is None:
        qst_key = f"qst_{session['id']}_{qid}"
        if qst_key not in st.session_state:
            st.session_state[qst_key] = time.time()

        if question["type"] == "single":
            chosen = st.radio(
                "Choose one",
                options=[o["id"] for o in question["options"]],
                format_func=lambda oid: f"{opt_by_id[oid]['label']}. {opt_by_id[oid]['text']}",
                key=f"runner_radio_{qid}",
                index=None,
            )
            disabled = chosen is None
            if st.button(
                "Submit",
                type="primary",
                key=f"runner_submit_{qid}",
                disabled=disabled,
            ):
                elapsed = int(time.time() - st.session_state[qst_key])
                record_answer(session["id"], qid, [chosen], correct_ids, elapsed)
                st.session_state.pop(qst_key, None)
                st.rerun()
        else:
            needed = len(correct_ids)
            st.caption(f"Select exactly {needed} options.")
            selected: list[str] = []
            for o in question["options"]:
                if st.checkbox(f"{o['label']}. {o['text']}", key=f"runner_cb_{qid}_{o['id']}"):
                    selected.append(o["id"])
            disabled = len(selected) != needed
            if st.button(
                "Submit",
                type="primary",
                key=f"runner_submit_{qid}",
                disabled=disabled,
            ):
                elapsed = int(time.time() - st.session_state[qst_key])
                record_answer(session["id"], qid, selected, correct_ids, elapsed)
                st.session_state.pop(qst_key, None)
                st.rerun()
    else:
        selected_ids = prior["selected_option_ids"] or []
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
        if st.button(
            next_label,
            type="primary",
            key=f"runner_next_{qid}",
            use_container_width=True,
        ):
            st.session_state[index_key] = index + 1
            st.rerun()


def render_summary(
    summary: dict,
    restart_label: str = "Start another",
    home_page: str = "pages/home.py",
) -> str | None:
    """Render the post-session summary card.

    Returns "restart" if user clicked the restart button (caller should drop
    the summary key + rerun), None otherwise. Switches to `home_page` if the
    user clicked Back to Home (so the caller never sees that path).
    """
    pct = summary["score_pct"]
    if summary["passed"]:
        st.success(
            f"Session complete: **{pct}%** ({summary['correct']}/{summary['total']}) -- passed"
        )
    else:
        st.error(
            f"Session complete: **{pct}%** ({summary['correct']}/{summary['total']}) -- below pass threshold"
        )
    minutes, seconds = divmod(summary["duration_seconds"], 60)
    st.caption(f"Time: {minutes}m {seconds}s")

    c1, c2 = st.columns(2)
    if c1.button(restart_label, type="primary", key="summary_restart"):
        return "restart"
    if c2.button("Back to home", key="summary_home"):
        st.switch_page(home_page)
    return None
