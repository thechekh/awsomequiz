"""Stats dashboard for the authenticated user.

Four sections:
  1. Top row -- 4 metric cards (unique seen / overall accuracy / streak / sessions).
  2. Score history -- line chart of timed-exam scores over time.
  3. Per-domain accuracy -- bar chart; degrades to an "untagged" notice while
     `questions.domain_id` is still nullable across the catalog.
  4. Recent sessions -- compact table.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.queries import (
    get_clf_certification,
    get_per_domain_accuracy,
    get_practice_streak,
    get_session_history,
    get_user_stats_summary,
)


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "--"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s"


def _format_started(ts: str) -> str:
    """Compact "YYYY-MM-DD HH:MM" from a Postgres ISO timestamp."""
    return ts[:16].replace("T", " ")


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()
cert = get_clf_certification()

st.title("Stats")

if not cert:
    st.error("Certification not seeded.")
    st.stop()

# ---------------------------------------------------------------------------
# Top row: 4 metrics
# ---------------------------------------------------------------------------

summary = get_user_stats_summary(user["id"], cert["id"])
streak = get_practice_streak(user["id"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Unique questions seen", summary["unique_seen"])
c2.metric(
    "Overall accuracy",
    f"{summary['overall_accuracy_pct']}%",
    help=f"{summary['total_correct']} correct out of {summary['total_attempts']} attempts",
)
c3.metric("Current streak", f"{streak} day" + ("" if streak == 1 else "s"))
c4.metric("Sessions completed", summary["sessions_completed"])

if summary["unique_seen"] == 0:
    st.info("Answer some questions first -- charts will populate as you practice.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Score history (timed exams only)
# ---------------------------------------------------------------------------

st.subheader("Timed-exam score history")
timed = get_session_history(user["id"], cert["id"], mode="timed", limit=50)
completed_timed = [s for s in timed if s["completed_at"] and s["score_pct"] is not None]
if completed_timed:
    df = (
        pd.DataFrame([
            {
                "Date": datetime.fromisoformat(s["completed_at"].replace("Z", "+00:00")),
                "Score %": float(s["score_pct"]),
            }
            for s in completed_timed
        ])
        .sort_values("Date")
        .set_index("Date")
    )
    st.line_chart(df, y="Score %")
    st.caption(f"Pass threshold: {cert['pass_threshold_pct']}%")
else:
    st.caption("No timed exams completed yet -- take one to see your score over time.")

st.divider()

# ---------------------------------------------------------------------------
# Per-domain accuracy
# ---------------------------------------------------------------------------

st.subheader("Accuracy by domain")
domains = get_per_domain_accuracy(user["id"], cert["id"])
tagged = [d for d in domains if d["code"] != "untagged" and d["attempts"] > 0]
untagged = next((d for d in domains if d["code"] == "untagged"), None)

if not tagged:
    if untagged and untagged["attempts"] > 0:
        st.info(
            f"Questions in this dump aren't tagged with domains yet, so all "
            f"**{untagged['attempts']}** of your attempts "
            f"({untagged['accuracy_pct']}% accuracy) live in the **Untagged** "
            f"bucket. Once domain tagging is implemented, this chart will "
            f"break out per domain."
        )
    else:
        st.caption("No per-domain data yet.")
else:
    df = pd.DataFrame([
        {"Domain": d["name"], "Accuracy %": d["accuracy_pct"]}
        for d in tagged
    ]).set_index("Domain")
    st.bar_chart(df, y="Accuracy %")
    if untagged and untagged["attempts"] > 0:
        st.caption(
            f"+ {untagged['attempts']} attempts in **Untagged** "
            f"({untagged['accuracy_pct']}%) -- not shown in the chart."
        )

st.divider()

# ---------------------------------------------------------------------------
# Recent sessions
# ---------------------------------------------------------------------------

st.subheader("Recent sessions")
recent = get_session_history(user["id"], cert["id"], limit=20)
if not recent:
    st.caption("No sessions yet.")
else:
    table = [
        {
            "Mode": s["mode"].replace("_", " ").title(),
            "Started": _format_started(s["started_at"]),
            "Questions": s["question_count"],
            "Score": f"{s['score_pct']}%" if s["score_pct"] is not None else "--",
            "Passed": (
                ("Yes" if s["passed"] else "No")
                if s["passed"] is not None
                else "In progress"
            ),
            "Duration": _format_duration(s.get("duration_seconds")),
        }
        for s in recent
    ]
    st.dataframe(table, hide_index=True, use_container_width=True)
