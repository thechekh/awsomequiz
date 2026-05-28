"""Home / landing page (authenticated only).

Layout:
    1. Welcome line + one-paragraph intro.
    2. Dark stat hero block -- certification, question count, pass threshold.
    3. Resume banners (if any unfinished sessions).
    4. Section: STUDY MODES  -> Practice / Timed / Review / Bookmarks.
    5. Section: REFERENCE    -> Flashcards / Stats.
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.db import get_supabase
from app.queries import (
    get_answered_question_ids,
    get_current_certification,
    get_display_name,
)
from app.session import (
    get_active_bookmarked_session,
    get_active_practice_session,
    get_active_review_session,
    get_active_timed_session,
)

user = current_user()
if not user:
    st.switch_page("pages/login.py")

apply_session_to_client()
cert = get_current_certification()

_display = get_display_name(user["id"], user.get("email") or "")
st.title(f"Welcome, {_display}")

if not cert:
    st.warning("No certifications seeded. Run `.\\dev.ps1 db-reset` to seed.")
    st.stop()

st.markdown(
    f'<div class="welcome-intro">'
    f"Practice the {cert['name']} ({cert['code']}) exam. "
    "Mix free practice and full timed simulations, drill questions you got wrong, "
    "or study with Anki-style flashcards. Your progress saves automatically across modes."
    "</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Dark stat hero block (the artifact's "Our Proof Points" pattern)
# ---------------------------------------------------------------------------

supabase = get_supabase()
q_count = (
    supabase.table("questions")
    .select("id", count="exact")
    .eq("certification_id", cert["id"])
    .execute()
).count or 0

st.markdown(
    f"""
    <div class="dark-stat-block">
      <div class="dark-stat-block-title">{cert['code']} — {cert['name']}</div>
      <div class="dark-stat-row">
        <div class="dark-stat-item">
          <div class="dark-stat-label">Questions available</div>
          <div class="dark-stat-value">{q_count}</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Pass threshold</div>
          <div class="dark-stat-value accent-emerald">{cert['pass_threshold_pct']}%</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Exam duration</div>
          <div class="dark-stat-value">{cert['duration_minutes']} min</div>
        </div>
        <div class="dark-stat-item">
          <div class="dark-stat-label">Exam length</div>
          <div class="dark-stat-value">{cert['question_count']} Q</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Resume banners across all modes
# ---------------------------------------------------------------------------

RESUME_MODES = [
    (get_active_practice_session, "practice", "Practice", "pages/practice.py", "info"),
    (get_active_timed_session, "timed", "Timed exam", "pages/timed_exam.py", "warning"),
    (get_active_review_session, "review", "Review", "pages/review.py", "info"),
    (get_active_bookmarked_session, "bookmarked", "Bookmarked", "pages/bookmarks.py", "info"),
]

shown_any = False
for fetch_fn, key, label, page, level in RESUME_MODES:
    sess = fetch_fn(user["id"])
    if not sess:
        continue
    answered = len(get_answered_question_ids(sess["id"]))
    msg = f"Unfinished **{label}** session: **{answered}/{sess['question_count']}** answered."
    if level == "warning":
        st.warning(msg)
    else:
        st.info(msg)
    if st.button(f"Resume {label.lower()}", type="primary", key=f"resume_{key}"):
        st.switch_page(page)
    shown_any = True

if shown_any:
    st.write("")  # small spacer

# ---------------------------------------------------------------------------
# Study modes section
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Study modes</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    if st.button("Start a practice session", type="primary", width="stretch"):
        st.switch_page("pages/practice.py")
    st.caption("Pick domain + count. Immediate feedback after each answer.")
with c2:
    if st.button("Start a timed exam", type="primary", width="stretch"):
        st.switch_page("pages/timed_exam.py")
    st.caption(
        f"{cert['question_count']}Q / {cert['duration_minutes']} min. "
        f"Mirrors the real {cert['code']} exam (pass at {cert['pass_threshold_pct']}%)."
    )

c3, c4 = st.columns(2)
with c3:
    if st.button("Review weak areas / missed", width="stretch"):
        st.switch_page("pages/review.py")
    st.caption("Drill questions you got wrong or accuracy < 70%.")
with c4:
    if st.button("Bookmarks", width="stretch"):
        st.switch_page("pages/bookmarks.py")
    st.caption("Manage saved questions and practice them.")

# ---------------------------------------------------------------------------
# Reference section
# ---------------------------------------------------------------------------

st.markdown('<div class="section-label">Reference &amp; insight</div>', unsafe_allow_html=True)

c5, c6 = st.columns(2)
with c5:
    if st.button("Flashcards", width="stretch"):
        st.switch_page("pages/flashcards.py")
    st.caption("Anki-style decks: AWS services, frameworks, basics.")
with c6:
    if st.button("Stats", width="stretch"):
        st.switch_page("pages/stats.py")
    st.caption("Accuracy trends, streaks, recent sessions.")
