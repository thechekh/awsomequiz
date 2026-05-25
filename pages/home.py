"""Home / landing page (authenticated only).

Shows the catalog at a glance, resume CTAs for any unfinished session across
modes, and quick-start buttons.
"""

from __future__ import annotations

import streamlit as st

from app.auth import apply_session_to_client, current_user
from app.db import get_supabase
from app.queries import get_answered_question_ids, get_clf_certification
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
cert = get_clf_certification()

st.title(f"Welcome, {user['email']}")

if not cert:
    st.warning("No CLF-C02 certification row found. Run `.\\dev.ps1 db-reset` to seed.")
    st.stop()

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
    st.divider()

# ---------------------------------------------------------------------------
# Quick-start CTAs
# ---------------------------------------------------------------------------

c1, c2 = st.columns(2)
with c1:
    if st.button("Start a practice session", type="primary", use_container_width=True):
        st.switch_page("pages/practice.py")
    st.caption("Pick domain + count. Immediate feedback after each answer.")
with c2:
    if st.button("Start a timed exam", type="primary", use_container_width=True):
        st.switch_page("pages/timed_exam.py")
    st.caption(
        f"{cert['question_count']}Q / {cert['duration_minutes']} min. "
        f"Mirrors real CLF-C02 (pass at {cert['pass_threshold_pct']}%)."
    )

c3, c4 = st.columns(2)
with c3:
    if st.button("Review weak areas / missed", use_container_width=True):
        st.switch_page("pages/review.py")
    st.caption("Drill questions you got wrong or accuracy < 70%.")
with c4:
    if st.button("Bookmarks", use_container_width=True):
        st.switch_page("pages/bookmarks.py")
    st.caption("Manage saved questions and practice them.")

c5, c6 = st.columns(2)
with c5:
    if st.button("Flashcards", use_container_width=True):
        st.switch_page("pages/flashcards.py")
    st.caption("Anki-style decks: AWS services, frameworks, basics.")
with c6:
    if st.button("Stats", use_container_width=True):
        st.switch_page("pages/stats.py")
    st.caption("Accuracy trends, streaks, recent sessions.")

st.divider()

# ---------------------------------------------------------------------------
# Catalog summary
# ---------------------------------------------------------------------------

supabase = get_supabase()
q_count = (
    supabase.table("questions")
    .select("id", count="exact")
    .eq("certification_id", cert["id"])
    .execute()
).count or 0

m1, m2, m3 = st.columns(3)
m1.metric("Certification", cert["code"])
m2.metric("Questions available", q_count)
m3.metric("Pass threshold", f"{cert['pass_threshold_pct']}%")

st.divider()

st.subheader("Coming soon")
st.markdown(
    "- **Production deploy** -- Streamlit Cloud + hosted Supabase guide (Phase 8)\n"
    "- **Domain tagging** -- per-domain accuracy stats will populate once questions are tagged"
)
