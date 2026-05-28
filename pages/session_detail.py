"""Per-question review of a single completed session.

Reached by clicking a row in the Stats page's "Recent sessions" table; the
session_id arrives via the `?id=` query param. Reuses `get_review_bundle`
(same helper that powers the timed-exam end-of-session review) so the
rendering is consistent across both entry points.
"""
from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.queries import (
    format_started_at,
    get_current_certification,
    get_review_bundle,
)

user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()

session_id = st.query_params.get("id")
if not session_id:
    st.warning("No session selected. Open one from the Stats page.")
    if st.button("Back to Stats"):
        st.switch_page("pages/stats.py")
    st.stop()

# Pull the session row directly (RLS scopes to this user).
from app.db import get_supabase  # local import avoids ordering churn

supabase = get_supabase()
sess_rows = (
    supabase.table("exam_sessions")
    .select(
        "id, mode, started_at, completed_at, score_pct, passed, "
        "question_count, duration_seconds, certification_id"
    )
    .eq("id", session_id)
    .eq("user_id", user["id"])
    .limit(1)
    .execute()
).data or []

if not sess_rows:
    st.error(
        "Session not found, or it belongs to a different account. "
        "Sessions are private to the user who created them."
    )
    if st.button("Back to Stats"):
        st.switch_page("pages/stats.py")
    st.stop()

sess = sess_rows[0]

st.title(f"{sess['mode'].replace('_', ' ').title()} session")
st.caption(f"Started {format_started_at(sess['started_at'])}")

cert = get_current_certification()
threshold = cert["pass_threshold_pct"] if cert else 70

# ---------------------------------------------------------------------------
# Top banner: score / pass / duration
# ---------------------------------------------------------------------------

if sess.get("score_pct") is None:
    st.info("This session wasn't completed -- no score to show.")
else:
    score = float(sess["score_pct"])
    correct = int(round(score * sess["question_count"] / 100))
    if sess["passed"]:
        st.success(
            f"PASSED -- **{score}%** ({correct} / {sess['question_count']})"
        )
    else:
        st.error(
            f"BELOW PASS THRESHOLD -- **{score}%** ({correct} / {sess['question_count']})"
        )

duration = sess.get("duration_seconds")
if duration is not None:
    minutes, seconds = divmod(int(duration), 60)
    st.caption(f"Time spent: {minutes}m {seconds}s")

st.divider()

c1, c2 = st.columns(2)
if c1.button("Back to Stats"):
    st.switch_page("pages/stats.py")
if c2.button("Home"):
    st.switch_page("pages/home.py")

# ---------------------------------------------------------------------------
# Per-question review (re-uses the timed-exam review-row renderer's shape)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Review")

bundle = get_review_bundle(session_id)
if not bundle:
    st.caption("No questions on this session (or all were dropped).")
    st.stop()

wrong = [r for r in bundle if not r["is_correct"]]
right = [r for r in bundle if r["is_correct"]]

tab_w, tab_r, tab_a = st.tabs([
    f"Wrong ({len(wrong)})",
    f"Correct ({len(right)})",
    f"All ({len(bundle)})",
])


def _render_row(row: dict) -> None:
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


for tab, rows in ((tab_w, wrong), (tab_r, right), (tab_a, bundle)):
    with tab:
        if not rows:
            st.caption("(none)")
        for row in rows:
            _render_row(row)
