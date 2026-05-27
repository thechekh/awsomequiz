"""Stats dashboard for the authenticated user.

Layout (post-redesign):
    1. Title
    2. Dark stat hero: 4 high-level metrics (unique seen, accuracy, streak, sessions)
    3. Section: Score history (line chart, timed only)
    4. Section: Accuracy by domain (bar chart + Untagged fallback message)
    5. Section: Recent sessions (last 20 in a dataframe)
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.queries import (
    get_current_certification,
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
    """Compact 'YYYY-MM-DD HH:MM' from a Postgres ISO timestamp."""
    return ts[:16].replace("T", " ")


user = current_user()
if not user:
    st.switch_page("pages/login.py")
apply_session_to_client()
cert = get_current_certification()

st.title("Stats")

if not cert:
    st.error("Certification not seeded.")
    st.stop()

summary = get_user_stats_summary(user["id"], cert["id"])
streak = get_practice_streak(user["id"])

# ---------------------------------------------------------------------------
# Dark stat hero -- 4 high-level metrics
# ---------------------------------------------------------------------------

streak_text = f"{streak} day" + ("" if streak == 1 else "s")
accuracy_class = "accent-emerald" if summary["overall_accuracy_pct"] >= 70 else "accent-amber"

st.markdown(
    f"""
    <div class="dark-stat-block">
      <div class="dark-stat-block-title">Your overall progress</div>
      <div class="dark-stat-row">
        <div class="dark-stat-item">
          <div class="dark-stat-label">Unique questions seen</div>
          <div class="dark-stat-value">{summary['unique_seen']}</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Overall accuracy</div>
          <div class="dark-stat-value {accuracy_class}">{summary['overall_accuracy_pct']}%</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Current streak</div>
          <div class="dark-stat-value">{streak_text}</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Sessions completed</div>
          <div class="dark-stat-value">{summary['sessions_completed']}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if summary["unique_seen"] == 0:
    st.info("Answer some questions first -- charts will populate as you practice.")
    st.stop()

# ---------------------------------------------------------------------------
# Score history (timed exams only)
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Score history (timed exams)</div>', unsafe_allow_html=True)
timed = get_session_history(user["id"], cert["id"], mode="timed", limit=50)
completed_timed = [s for s in timed if s["completed_at"] and s["score_pct"] is not None]

with st.container(border=True):
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

# ---------------------------------------------------------------------------
# Per-domain accuracy
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Accuracy by domain</div>', unsafe_allow_html=True)
domains = get_per_domain_accuracy(user["id"], cert["id"])
tagged = [d for d in domains if d["code"] != "untagged" and d["attempts"] > 0]
untagged = next((d for d in domains if d["code"] == "untagged"), None)

with st.container(border=True):
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

# ---------------------------------------------------------------------------
# Recent sessions
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Recent sessions</div>', unsafe_allow_html=True)
recent = get_session_history(user["id"], cert["id"], limit=20)

with st.container(border=True):
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
