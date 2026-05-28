"""Timed exam page: full-exam simulation. Duration / question count / pass
threshold all come from the active certification row (CLF-C02 = 90 min, 65 Q,
70%; DVA-C02 = 130 min, 65 Q, 72%; etc.).

State machine:
  1. Summary in state    -> render review screen with explanations.
  2. No session anywhere -> show Start form (or Resume if DB has an incomplete one).
  3. Active session      -> exam runner: timer + sidebar grid + current question
                            (no per-question feedback). Submit OR auto-submit on timeout.

Timer is a `st.fragment(run_every="1s")` so the countdown updates without
re-rendering the whole exam. The deadline is `started_at + duration_minutes`
read from the session row (not the client clock), so a browser-tab clock skew
can't cheat extra time.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.queries import (
    REPORT_REASONS,
    format_started_at,
    get_answered_question_ids,
    get_current_certification,
    get_question_with_options,
    get_review_bundle,
    get_user_answer,
    is_bookmarked,
    report_question,
    toggle_bookmark,
)
from app.session import (
    abandon_session,
    complete_session,
    get_active_timed_session,
    record_answer,
    start_timed_session,
)


_REPORT_LABELS = {
    "incorrect_answer": "Answer is wrong",
    "typo": "Typo / formatting",
    "ambiguous": "Question is ambiguous",
    "outdated": "Outdated / no longer accurate",
    "other": "Other",
}


@st.dialog("Report a problem")
def _timed_report_dialog(question_id: str, user_id: str) -> None:
    """Modal that posts to question_reports during a timed exam."""
    st.caption("Reports are reviewed offline; this exam continues normally.")
    reason = st.radio(
        "Reason",
        options=list(REPORT_REASONS),
        format_func=lambda r: _REPORT_LABELS.get(r, r),
        key=f"timed_report_reason_{question_id}",
    )
    details = st.text_area(
        "Details (optional)",
        key=f"timed_report_details_{question_id}",
    )
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch", key=f"timed_report_cancel_{question_id}"):
        st.rerun()
    if c2.button(
        "Submit report",
        type="primary",
        width="stretch",
        key=f"timed_report_submit_{question_id}",
    ):
        try:
            report_question(user_id, question_id, reason, details or None)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not submit: {exc}")
            return
        st.success("Report submitted.")
        st.rerun()

TIMED_SESSION_KEY = "timed_session"
TIMED_INDEX_KEY = "timed_index"
TIMED_SUMMARY_KEY = "timed_summary"
TIMED_AUTO_SUBMITTED_KEY = "timed_auto_submitted"


# ---------------------------------------------------------------------------
# Helpers (top of module so callbacks can see them)
# ---------------------------------------------------------------------------


def _clear_timed_state() -> None:
    for k in list(st.session_state.keys()):
        if k.startswith("timed_"):
            st.session_state.pop(k, None)


def _first_unanswered_index(session_row: dict) -> int:
    answered = get_answered_question_ids(session_row["id"])
    for i, qid in enumerate(session_row["question_ids"]):
        if qid not in answered:
            return i
    return 0  # all answered -> show first


def _deadline(session_row: dict, cert: dict) -> datetime:
    started = datetime.fromisoformat(session_row["started_at"].replace("Z", "+00:00"))
    return started + timedelta(minutes=cert["duration_minutes"])


def _finalize(session_id: str) -> None:
    """Call complete_session, store summary, clear runner state, and rerun app."""
    summary = complete_session(session_id)
    st.session_state[TIMED_SUMMARY_KEY] = summary
    for k in list(st.session_state.keys()):
        # Drop runner state but keep summary
        if k.startswith("timed_") and k != TIMED_SUMMARY_KEY:
            st.session_state.pop(k, None)
    st.rerun(scope="app")


@st.fragment(run_every="1s")
def _render_timer(deadline_iso: str, session_id: str) -> None:
    """Live countdown. Auto-submits the exam when it hits zero."""
    now = datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(deadline_iso)
    remaining = max(0, int((deadline - now).total_seconds()))
    minutes, seconds = divmod(remaining, 60)
    label = f"{minutes:02d}:{seconds:02d}"

    if remaining <= 0:
        # Guard against the fragment double-firing during the rerun window.
        if not st.session_state.get(TIMED_AUTO_SUBMITTED_KEY):
            st.session_state[TIMED_AUTO_SUBMITTED_KEY] = True
            _finalize(session_id)
        return

    if remaining < 600:
        st.markdown(f":red[**Time remaining: {label}**]")
    else:
        st.markdown(f"**Time remaining:** {label}")


@st.dialog("Submit exam?")
def _submit_dialog(session_row: dict) -> None:
    answered = len(get_answered_question_ids(session_row["id"]))
    total = session_row["question_count"]
    st.write(f"You've answered **{answered} / {total}** questions.")
    if answered < total:
        st.warning(
            f"{total - answered} questions are still unanswered. "
            "Unanswered questions are scored as wrong."
        )
    st.write("Submit and view your score?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Submit final", type="primary", width="stretch"):
        _finalize(session_row["id"])


def _render_review(summary: dict) -> None:
    """Final-score banner + per-question review with explanations."""
    score = summary["score_pct"]
    if summary["passed"]:
        st.success(f"PASSED -- **{score}%** ({summary['correct']} / {summary['total']})")
        # Celebrate on pass; once per summary render to avoid repeat firing.
        ballooned_key = f"timed_passed_celebrated_{summary['session_id']}"
        if not st.session_state.get(ballooned_key):
            st.session_state[ballooned_key] = True
            st.balloons()
    else:
        st.error(f"BELOW PASS THRESHOLD -- **{score}%** ({summary['correct']} / {summary['total']})")
    minutes, seconds = divmod(summary["duration_seconds"], 60)
    st.caption(f"Time spent: {minutes}m {seconds}s   Answered: {summary['answered']} / {summary['total']}")

    c1, c2 = st.columns(2)
    if c1.button("Start a new exam", type="primary"):
        _clear_timed_state()
        st.rerun()
    if c2.button("Back to home"):
        _clear_timed_state()
        st.switch_page("pages/home.py")

    st.divider()
    st.subheader("Review")

    bundle = get_review_bundle(summary["session_id"])
    wrong = [r for r in bundle if not r["is_correct"]]
    right = [r for r in bundle if r["is_correct"]]

    tab_w, tab_r, tab_a = st.tabs([
        f"Wrong ({len(wrong)})",
        f"Correct ({len(right)})",
        f"All ({len(bundle)})",
    ])
    for tab, rows in ((tab_w, wrong), (tab_r, right), (tab_a, bundle)):
        with tab:
            if not rows:
                st.caption("(none)")
            for row in rows:
                _render_review_row(row)


def _render_review_row(row: dict) -> None:
    title = f"Q{row['index'] + 1}: {row['stem'][:80]}"
    if len(row["stem"]) > 80:
        title += "..."
    if row["is_correct"]:
        marker = "✅"
    elif row["unanswered"]:
        marker = "⬜"
    else:
        marker = "❌"
    with st.expander(f"{marker} {title}"):
        st.markdown(row["stem"])
        st.write("")
        for o in row["options"]:
            was_selected = o["id"] in row["selected_option_ids"]
            is_right = o["is_correct"]
            opt_marker = "✅" if is_right else "❌"
            tag = '<span class="opt-tag">(your answer)</span>' if was_selected else ""
            row_class = "opt-row"
            if is_right:
                row_class += " correct"
            elif was_selected:
                row_class += " wrong"
            st.markdown(
                f'<div class="{row_class}">{opt_marker} <b>{o["label"]}. {o["text"]}</b>{tag}</div>',
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


# ---------------------------------------------------------------------------
# Main page flow
# ---------------------------------------------------------------------------

user = current_user()
if not user:
    st.switch_page("pages/login.py")

apply_session_to_client()
cert = get_current_certification()

st.title("Timed exam")

if not cert:
    st.error("Certification not seeded. Run db-reset.")
    st.stop()

# 1) Just completed -> review screen
if summary := st.session_state.get(TIMED_SUMMARY_KEY):
    _render_review(summary)
    st.stop()

# 2) Detect / resume / start
session = st.session_state.get(TIMED_SESSION_KEY)
if session is None:
    existing = get_active_timed_session(user["id"])
    if existing:
        # Auto-finalize if the in-DB deadline has already passed.
        if datetime.now(timezone.utc) > _deadline(existing, cert):
            _finalize(existing["id"])
        answered_count = len(get_answered_question_ids(existing["id"]))
        st.info(
            f"You have an unfinished exam: "
            f"**{answered_count}/{existing['question_count']}** answered, "
            f"started {format_started_at(existing['started_at'])}."
        )
        c1, c2 = st.columns(2)
        if c1.button("Resume exam", type="primary"):
            st.session_state[TIMED_SESSION_KEY] = existing
            st.session_state[TIMED_INDEX_KEY] = _first_unanswered_index(existing)
            st.rerun()
        if c2.button("Abandon and start new"):
            abandon_session(existing["id"])
            st.rerun()
        st.stop()

if session is None:
    st.markdown(
        f"Mirrors the real **{cert['code']}** exam:\n\n"
        f"- **{cert['question_count']} questions**, **{cert['duration_minutes']} minutes**\n"
        f"- Pass threshold: **{cert['pass_threshold_pct']}%**\n"
        f"- No per-question feedback during the exam\n"
        f"- You can navigate freely between questions and revise answers\n"
        f"- Auto-submits when the timer hits zero"
    )
    if st.button("Start exam", type="primary"):
        try:
            new = start_timed_session(user["id"], cert["id"])
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
        st.session_state[TIMED_SESSION_KEY] = new
        st.session_state[TIMED_INDEX_KEY] = 0
        st.rerun()
    st.stop()

# 3) Active exam runner
question_ids = session["question_ids"]
total = len(question_ids)
index = max(0, min(st.session_state.get(TIMED_INDEX_KEY, 0), total - 1))

answered_ids = get_answered_question_ids(session["id"])
deadline_iso = _deadline(session, cert).isoformat()

# Sidebar: timer + question grid + submit
with st.sidebar:
    st.divider()
    _render_timer(deadline_iso, session["id"])
    st.divider()
    st.caption(f"**Answered: {len(answered_ids)} / {total}**")

    # 4 per row gives each button ~70 px in a typical ~310 px sidebar -- a bit
    # more breathing room than the previous 5-per-row (was cramped at <1366 px).
    n_per_row = 4
    for row_start in range(0, total, n_per_row):
        cols = st.columns(n_per_row)
        for j in range(n_per_row):
            q_idx = row_start + j
            if q_idx >= total:
                break
            qid = question_ids[q_idx]
            is_current = q_idx == index
            is_answered = qid in answered_ids
            prefix = "v " if is_answered else "  "
            btn_type = "primary" if is_current else "secondary"
            with cols[j]:
                if st.button(
                    f"{prefix}{q_idx + 1}",
                    key=f"timed_grid_{q_idx}",
                    type=btn_type,
                    width="stretch",
                ):
                    st.session_state[TIMED_INDEX_KEY] = q_idx
                    st.rerun()

    st.divider()
    if st.button("Submit exam", type="primary", width="stretch"):
        _submit_dialog(session)

# Main pane: current question
qid = question_ids[index]
question = get_question_with_options(qid)
opt_by_id = {o["id"]: o for o in question["options"]}
correct_ids = [o["id"] for o in question["options"] if o["is_correct"]]
prior = get_user_answer(session["id"], qid)
prior_selected: list[str] = (prior or {}).get("selected_option_ids") or []

hcol, bcol, rcol = st.columns([6, 1, 1])
hcol.subheader(f"Question {index + 1} of {total}")

bookmarked = is_bookmarked(user["id"], qid)
bm_label = "Bookmarked" if bookmarked else "Bookmark"
if bcol.button(bm_label, key=f"timed_bm_{qid}", width="stretch"):
    toggle_bookmark(user["id"], qid)
    st.rerun()
if rcol.button(
    "Report",
    key=f"timed_report_btn_{qid}",
    width="stretch",
    help="Flag a problem with this question.",
):
    _timed_report_dialog(qid, user["id"])

# Record first-view timestamp per question so we can capture time-on-question
# on Save. Survives navigation back-and-forth; cleared after the answer lands.
viewed_key = f"timed_viewed_{qid}"
if viewed_key not in st.session_state:
    st.session_state[viewed_key] = time.time()

st.markdown(question["stem"])

if question["type"] == "single":
    options_ids = [o["id"] for o in question["options"]]
    default_idx = options_ids.index(prior_selected[0]) if prior_selected else None
    chosen_id = st.radio(
        "Choose one",
        options=options_ids,
        format_func=lambda oid: f"{opt_by_id[oid]['label']}. {opt_by_id[oid]['text']}",
        key=f"timed_radio_{qid}",
        index=default_idx,
    )
    chosen: list[str] | None = [chosen_id] if chosen_id is not None else None
else:
    needed = len(correct_ids)
    st.caption(f"Select exactly {needed} options.")
    picked: list[str] = []
    for o in question["options"]:
        default = o["id"] in prior_selected
        if st.checkbox(
            f"{o['label']}. {o['text']}",
            value=default,
            key=f"timed_cb_{qid}_{o['id']}",
        ):
            picked.append(o["id"])
    chosen = picked if len(picked) == needed else None

# Navigation row
prev_col, save_col, next_col = st.columns(3)
if prev_col.button("Previous", disabled=index == 0, key=f"timed_prev_{qid}", width="stretch"):
    st.session_state[TIMED_INDEX_KEY] = index - 1
    st.rerun()

save_label = "Save & next" if index < total - 1 else "Save"
if save_col.button(
    save_label,
    type="primary",
    disabled=chosen is None,
    key=f"timed_save_{qid}",
    width="stretch",
):
    elapsed = int(time.time() - st.session_state.get(viewed_key, time.time()))
    record_answer(session["id"], qid, chosen, correct_ids, max(elapsed, 0))
    st.session_state.pop(viewed_key, None)
    if index < total - 1:
        st.session_state[TIMED_INDEX_KEY] = index + 1
    st.rerun()

if next_col.button(
    "Next",
    disabled=index >= total - 1,
    key=f"timed_next_{qid}",
    width="stretch",
):
    st.session_state[TIMED_INDEX_KEY] = index + 1
    st.rerun()
