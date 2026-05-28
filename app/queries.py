"""Query helpers for the practice modes.

All functions go through `get_supabase()`, which returns the cached client
already wearing the user's session (RLS applies). Static reference data is
cached with `@st.cache_data` per the brief's free-tier constraint.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import streamlit as st

from app.db import get_supabase

CACHE_TTL_REFERENCE = 60 * 60  # 1 h: cert, domains -- ~never change
CACHE_TTL_QUESTION = 5 * 60     # 5 min: question text / options


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


CURRENT_CERT_CODE_KEY = "current_cert_code"
DEFAULT_CERT_CODE = "CLF-C02"

_CERT_FIELDS = "id, code, name, question_count, duration_minutes, pass_threshold_pct"


@st.cache_data(ttl=CACHE_TTL_REFERENCE)
def get_certification_by_code(code: str) -> dict | None:
    """Fetch one certification row by its code (CLF-C02, DVA-C02, ...). None if missing."""
    supabase = get_supabase()
    rows = (
        supabase.table("certifications")
        .select(_CERT_FIELDS)
        .eq("code", code)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


@st.cache_data(ttl=CACHE_TTL_REFERENCE)
def list_certifications_with_questions() -> list[dict]:
    """Return certifications that have at least one active question.

    Two round-trips (distinct cert IDs from `questions`, then look those IDs
    up in `certifications`). Cached at the reference TTL because adding a
    question bank to a cert is a deploy-time event, not a per-request thing.
    """
    supabase = get_supabase()
    rows = (
        supabase.table("questions")
        .select("certification_id")
        .eq("is_active", True)
        .limit(10000)
        .execute()
    ).data or []
    cert_ids = list({r["certification_id"] for r in rows})
    if not cert_ids:
        return []
    return (
        supabase.table("certifications")
        .select(_CERT_FIELDS)
        .in_("id", cert_ids)
        .order("code")
        .execute()
    ).data or []


def get_current_certification() -> dict | None:
    """Return the cert the user is currently practicing.

    Resolution order:
      1. session_state[CURRENT_CERT_CODE_KEY] (set by the picker UI)
      2. profiles.current_cert_code (logged-in users, persisted across sessions)
      3. DEFAULT_CERT_CODE fallback (CLF-C02)

    The resolved code is cached in session_state so subsequent calls skip
    the profile lookup. None if the resolved cert doesn't exist (e.g. a
    stale cookie pointing at a deleted cert -- caller should re-prompt).
    """
    code = st.session_state.get(CURRENT_CERT_CODE_KEY)
    if not code:
        # Defer the import: queries -> auth -> queries would otherwise circle.
        from app.auth import current_user

        user = current_user()
        if user:
            supabase = get_supabase()
            rows = (
                supabase.table("profiles")
                .select("current_cert_code")
                .eq("id", user["id"])
                .limit(1)
                .execute()
            ).data or []
            if rows and rows[0].get("current_cert_code"):
                code = rows[0]["current_cert_code"]
        if not code:
            code = DEFAULT_CERT_CODE
        st.session_state[CURRENT_CERT_CODE_KEY] = code
    return get_certification_by_code(code)


def set_current_certification(code: str) -> None:
    """Switch the active cert. Updates session_state and (if logged in) profile."""
    st.session_state[CURRENT_CERT_CODE_KEY] = code
    from app.auth import current_user

    user = current_user()
    if user:
        supabase = get_supabase()
        supabase.table("profiles").update(
            {"current_cert_code": code},
        ).eq("id", user["id"]).execute()
    # Cache invalidation: the per-cert stats summaries pin to the old cert id;
    # the new cert is a different row so cache lookups won't collide, but the
    # sidebar's mini-stats panel reads the OLD value once before the next
    # render -- a single rerun after this call fixes that. Callers handle it.


@st.cache_data(ttl=60)
def get_display_name(user_id: str, email: str) -> str:
    """Return the user's display name: profiles.username if set, else email-local-part.

    Used in the welcome heading and sidebar caption so the user doesn't have to
    expose their full email address on screen shares. Cached briefly so a name
    change on /account propagates within a minute.
    """
    if not user_id:
        return email or "(unknown)"
    try:
        supabase = get_supabase()
        rows = (
            supabase.table("profiles")
            .select("username")
            .eq("id", user_id)
            .limit(1)
            .execute()
        ).data or []
        username = (rows[0].get("username") if rows else None) or ""
        if username.strip():
            return username.strip()
    except Exception:  # noqa: BLE001 -- fall back to email if the lookup fails
        pass
    return (email.split("@", 1)[0] if email else "") or email or "(unknown)"


@st.cache_data(ttl=CACHE_TTL_REFERENCE)
def list_domains(certification_id: str) -> list[dict]:
    """Return domain rows for a certification, ordered for display."""
    supabase = get_supabase()
    return (
        supabase.table("domains")
        .select("id, code, name, weight, display_order")
        .eq("certification_id", certification_id)
        .order("display_order")
        .execute()
    ).data or []


# ---------------------------------------------------------------------------
# Question selection
# ---------------------------------------------------------------------------


def pick_question_ids(
    certification_id: str,
    count: int | None,
    domain_ids: list[str] | None = None,
    shuffle: bool = True,
) -> list[str]:
    """Pick a list of active question IDs.

    Args:
        count: None means "all matching"; otherwise cap to `count`.
        shuffle: True (default) returns random order; False returns
                 questions sorted by external_id (the source's question_number,
                 numerically when parseable) so the user can practice the whole
                 set in deterministic order.

    PostgREST doesn't expose `random()` or numeric cast in `order`, so both
    shuffling and numeric sorting happen client-side. For <1000 questions
    per certification this is negligible.
    """
    supabase = get_supabase()
    query = (
        supabase.table("questions")
        .select("id, external_id")
        .eq("certification_id", certification_id)
        .eq("is_active", True)
    )
    if domain_ids:
        query = query.in_("domain_id", domain_ids)
    rows = query.limit(10000).execute().data or []

    if shuffle:
        ids = [row["id"] for row in rows]
        random.shuffle(ids)
    else:
        # Sort by external_id numerically when possible so Q2 < Q10 (lex
        # order would put "10" before "2").
        def _key(row: dict) -> tuple[int, str]:
            ext = row.get("external_id") or ""
            try:
                return (0, f"{int(ext):010d}")
            except (ValueError, TypeError):
                return (1, ext)
        rows.sort(key=_key)
        ids = [row["id"] for row in rows]

    if count is not None:
        ids = ids[:count]
    return ids


@st.cache_data(ttl=CACHE_TTL_QUESTION)
def get_question_with_options(question_id: str) -> dict:
    """Fetch one question + its options, ordered A-F."""
    supabase = get_supabase()
    q = (
        supabase.table("questions")
        .select("id, stem, type, version")
        .eq("id", question_id)
        .single()
        .execute()
    ).data
    opts = (
        supabase.table("options")
        .select("id, label, text, is_correct, explanation_detailed, related_context")
        .eq("question_id", question_id)
        .order("label")
        .execute()
    ).data or []
    return {**q, "options": opts}


# ---------------------------------------------------------------------------
# Answer state (per session)
# ---------------------------------------------------------------------------


def get_answered_question_ids(session_id: str) -> set[str]:
    """Return the set of question IDs already answered in this session."""
    supabase = get_supabase()
    rows = (
        supabase.table("user_answers")
        .select("question_id")
        .eq("session_id", session_id)
        .execute()
    ).data or []
    return {row["question_id"] for row in rows}


def get_user_answer(session_id: str, question_id: str) -> dict | None:
    """Return the user_answers row for this session+question, or None."""
    supabase = get_supabase()
    rows = (
        supabase.table("user_answers")
        .select("selected_option_ids, is_correct, time_spent_seconds, answered_at")
        .eq("session_id", session_id)
        .eq("question_id", question_id)
        .execute()
    ).data or []
    return rows[0] if rows else None


def get_review_bundle(session_id: str) -> list[dict]:
    """Fetch everything needed for an end-of-session review screen.

    Three round-trips total (questions, options, answers) instead of N per
    question -- matters for timed-exam reviews with 65 questions.
    """
    supabase = get_supabase()
    sess = (
        supabase.table("exam_sessions")
        .select("question_ids")
        .eq("id", session_id)
        .single()
        .execute()
    ).data
    qids = sess["question_ids"] or []
    if not qids:
        return []

    questions = (
        supabase.table("questions")
        .select("id, stem, type")
        .in_("id", qids)
        .execute()
    ).data or []
    options = (
        supabase.table("options")
        .select("question_id, id, label, text, is_correct, explanation_detailed, related_context")
        .in_("question_id", qids)
        .order("label")
        .execute()
    ).data or []
    answers = (
        supabase.table("user_answers")
        .select("question_id, selected_option_ids, is_correct, time_spent_seconds")
        .eq("session_id", session_id)
        .execute()
    ).data or []

    q_by_id = {q["id"]: q for q in questions}
    opts_by_q: dict[str, list[dict]] = {}
    for o in options:
        opts_by_q.setdefault(o["question_id"], []).append(o)
    ans_by_q = {a["question_id"]: a for a in answers}

    bundle: list[dict] = []
    for i, qid in enumerate(qids):
        q = q_by_id.get(qid)
        if not q:
            continue
        ans = ans_by_q.get(qid)
        bundle.append({
            "index": i,
            "question_id": qid,
            "stem": q["stem"],
            "type": q["type"],
            "options": opts_by_q.get(qid, []),
            "selected_option_ids": (ans or {}).get("selected_option_ids") or [],
            "is_correct": bool(ans and ans["is_correct"]),
            "unanswered": ans is None,
        })
    return bundle


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------


def is_bookmarked(user_id: str, question_id: str) -> bool:
    supabase = get_supabase()
    rows = (
        supabase.table("bookmarks")
        .select("question_id")
        .eq("user_id", user_id)
        .eq("question_id", question_id)
        .limit(1)
        .execute()
    ).data or []
    return len(rows) > 0


def toggle_bookmark(user_id: str, question_id: str) -> bool:
    """Flip the bookmark state. Returns the new state."""
    supabase = get_supabase()
    if is_bookmarked(user_id, question_id):
        (
            supabase.table("bookmarks")
            .delete()
            .eq("user_id", user_id)
            .eq("question_id", question_id)
            .execute()
        )
        return False
    supabase.table("bookmarks").insert({
        "user_id": user_id,
        "question_id": question_id,
    }).execute()
    return True


def delete_bookmark(user_id: str, question_id: str) -> None:
    supabase = get_supabase()
    (
        supabase.table("bookmarks")
        .delete()
        .eq("user_id", user_id)
        .eq("question_id", question_id)
        .execute()
    )


def list_bookmarks(user_id: str, certification_id: str) -> list[dict]:
    """Return the user's bookmarks for a certification, with question stems for display."""
    supabase = get_supabase()
    rows = (
        supabase.table("bookmarks")
        .select("question_id, note, created_at, questions(id, stem, type)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    ).data or []
    out: list[dict] = []
    for r in rows:
        q = r.get("questions")
        if not q or q.get("id") is None:
            # Question deleted -- skip orphaned bookmark
            continue
        out.append({
            "question_id": r["question_id"],
            "note": r.get("note"),
            "created_at": r["created_at"],
            "stem": q["stem"],
            "type": q["type"],
        })
    # Filter to the cert via a separate lookup (PostgREST nested-select doesn't filter parent).
    cert_qids = {
        row["id"] for row in (
            supabase.table("questions")
            .select("id")
            .eq("certification_id", certification_id)
            .in_("id", [r["question_id"] for r in out])
            .execute()
        ).data or []
    } if out else set()
    return [r for r in out if r["question_id"] in cert_qids]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

REPORT_REASONS = ("incorrect_answer", "typo", "ambiguous", "outdated", "other")


def format_started_at(iso_ts: str | None) -> str:
    """Format a Postgres ISO timestamp like '2026-05-26T14:43:43.315096+00:00'
    into a compact 'YYYY-MM-DD HH:MM:SS' display string. Returns '--' for None."""
    if not iso_ts:
        return "--"
    return iso_ts[:19].replace("T", " ")


# ---------------------------------------------------------------------------
# Mode-specific question selection (Phase 6)
# ---------------------------------------------------------------------------


def _cert_question_ids(certification_id: str) -> list[str]:
    supabase = get_supabase()
    rows = (
        supabase.table("questions")
        .select("id")
        .eq("certification_id", certification_id)
        .eq("is_active", True)
        .limit(10000)
        .execute()
    ).data or []
    return [r["id"] for r in rows]


CACHE_TTL_PICK = 30  # Short -- post-session UI feedback should feel fresh.


@st.cache_data(ttl=CACHE_TTL_PICK)
def _weak_area_question_ids_cached(
    user_id: str,
    certification_id: str,
    threshold_pct: int,
    min_attempts: int,
) -> list[str]:
    """Cached part of weak-area selection (no shuffle, no count cap)."""
    cert_qids = _cert_question_ids(certification_id)
    if not cert_qids:
        return []
    supabase = get_supabase()
    stats_rows = (
        supabase.table("question_stats")
        .select("question_id, times_seen, times_correct")
        .eq("user_id", user_id)
        .limit(10000)
        .execute()
    ).data or []
    stats_by_q = {s["question_id"]: s for s in stats_rows}

    weak: list[str] = []
    for qid in cert_qids:
        s = stats_by_q.get(qid)
        if s is None:
            weak.append(qid)
            continue
        if s["times_seen"] < min_attempts:
            continue
        accuracy = (s["times_correct"] / s["times_seen"]) * 100
        if accuracy < threshold_pct:
            weak.append(qid)
    return weak


def pick_weak_area_question_ids(
    user_id: str,
    certification_id: str,
    count: int | None = None,
    threshold_pct: int = 70,
    min_attempts: int = 3,
) -> list[str]:
    """Pick questions where the user's accuracy is below `threshold_pct` after
    at least `min_attempts` attempts, OR questions they've never seen.

    Unseen questions are included because the brief says weak-areas should
    surface knowledge gaps -- both confirmed-weak and uncovered-territory.

    The heavy lifting (cert qids + per-user stats fetch) is cached for 30s
    via `_weak_area_question_ids_cached`; the shuffle/count cap happens
    outside the cache so each call returns a fresh sample.
    """
    weak = list(_weak_area_question_ids_cached(
        user_id, certification_id, threshold_pct, min_attempts,
    ))
    random.shuffle(weak)
    if count is not None:
        weak = weak[:count]
    return weak


@st.cache_data(ttl=CACHE_TTL_PICK)
def _missed_question_ids_cached(user_id: str, certification_id: str) -> list[str]:
    """Cached part of missed-question selection (no shuffle, no count cap)."""
    cert_qid_set = set(_cert_question_ids(certification_id))
    if not cert_qid_set:
        return []

    supabase = get_supabase()
    session_rows = (
        supabase.table("exam_sessions")
        .select("id")
        .eq("user_id", user_id)
        .eq("certification_id", certification_id)
        .limit(10000)
        .execute()
    ).data or []
    session_ids = [s["id"] for s in session_rows]
    if not session_ids:
        return []

    answers = (
        supabase.table("user_answers")
        .select("question_id")
        .in_("session_id", session_ids)
        .eq("is_correct", False)
        .limit(10000)
        .execute()
    ).data or []
    return list({a["question_id"] for a in answers if a["question_id"] in cert_qid_set})


def pick_missed_question_ids(
    user_id: str,
    certification_id: str,
    count: int | None = None,
) -> list[str]:
    """Pick distinct questions the user has gotten wrong in any past session.

    Uses user_answers directly so this reflects the user's *last submitted*
    answer per session (works for both practice and timed-with-revisions).
    Inner fetch is cached for 30s; shuffle + slice happen outside so each
    call to start a session gets a fresh random sample.
    """
    missed = list(_missed_question_ids_cached(user_id, certification_id))
    random.shuffle(missed)
    if count is not None:
        missed = missed[:count]
    return missed


def pick_bookmarked_question_ids(
    user_id: str,
    certification_id: str,
    count: int | None = None,
) -> list[str]:
    """Pick questions the user has bookmarked in this certification."""
    supabase = get_supabase()
    rows = (
        supabase.table("bookmarks")
        .select("question_id")
        .eq("user_id", user_id)
        .limit(10000)
        .execute()
    ).data or []
    bm_qids = [r["question_id"] for r in rows]
    if not bm_qids:
        return []
    # Filter to this certification's active questions only.
    cert_rows = (
        supabase.table("questions")
        .select("id")
        .eq("certification_id", certification_id)
        .eq("is_active", True)
        .in_("id", bm_qids)
        .limit(10000)
        .execute()
    ).data or []
    qids = [r["id"] for r in cert_rows]
    random.shuffle(qids)
    if count is not None:
        qids = qids[:count]
    return qids


def report_question(user_id: str, question_id: str, reason: str, details: str | None) -> None:
    """File a question report via the SECURITY DEFINER RPC.

    The direct INSERT path kept tripping `question_reports` RLS in prod even
    after `set_session` + `postgrest.auth()` (see migration 0010). The RPC
    forces `user_id = auth.uid()` server-side so we can't be tricked into
    filing under another identity, and bypasses the policy that wouldn't
    pass for plain inserts.

    `user_id` arg is kept in the signature for backward compatibility but
    isn't sent over the wire -- the server reads it from the JWT.
    """
    del user_id  # use server-side auth.uid() instead
    if reason not in REPORT_REASONS:
        raise ValueError(f"Unknown report reason: {reason}")
    import streamlit as _st
    session = _st.session_state.get("supabase_session") or {}
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    if not access_token:
        raise RuntimeError("No active session; cannot file report.")
    supabase = get_supabase()
    supabase.auth.set_session(access_token, refresh_token)
    supabase.postgrest.auth(access_token)
    supabase.rpc(
        "submit_question_report",
        {
            "p_question_id": question_id,
            "p_reason": reason,
            "p_details": details or None,
        },
    ).execute()


# ---------------------------------------------------------------------------
# Stats (Phase 7)
# ---------------------------------------------------------------------------

CACHE_TTL_STATS = 30  # short so practice -> stats feedback feels live


@st.cache_data(ttl=CACHE_TTL_STATS)
def get_user_stats_summary(user_id: str, certification_id: str) -> dict:
    """Per-user rollup across question_stats + exam_sessions for one cert.

    Returns:
        unique_seen          -- distinct questions ever answered
        total_attempts       -- sum of times_seen across those questions
        total_correct        -- sum of times_correct
        overall_accuracy_pct -- 0.0 if no attempts
        sessions_completed   -- count of exam_sessions with completed_at set
    """
    supabase = get_supabase()
    cert_qids = set(_cert_question_ids(certification_id))
    stats = (
        supabase.table("question_stats")
        .select("question_id, times_seen, times_correct")
        .eq("user_id", user_id)
        .limit(10000)
        .execute()
    ).data or []
    relevant = [s for s in stats if s["question_id"] in cert_qids]
    total_attempts = sum(s["times_seen"] for s in relevant)
    total_correct = sum(s["times_correct"] for s in relevant)
    accuracy = (total_correct / total_attempts * 100) if total_attempts else 0.0

    completed = (
        supabase.table("exam_sessions")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("certification_id", certification_id)
        .not_.is_("completed_at", "null")
        .execute()
    )
    sessions_completed = completed.count or 0

    return {
        "unique_seen": len(relevant),
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy_pct": round(accuracy, 1),
        "sessions_completed": sessions_completed,
    }


def get_session_history(
    user_id: str,
    certification_id: str,
    mode: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Recent sessions, newest first. Not cached -- users expect freshness here."""
    supabase = get_supabase()
    q = (
        supabase.table("exam_sessions")
        .select(
            "id, mode, started_at, completed_at, score_pct, passed, "
            "question_count, duration_seconds"
        )
        .eq("user_id", user_id)
        .eq("certification_id", certification_id)
        .order("started_at", desc=True)
        .limit(limit)
    )
    if mode:
        q = q.eq("mode", mode)
    return q.execute().data or []


@st.cache_data(ttl=CACHE_TTL_STATS)
def get_per_domain_accuracy(user_id: str, certification_id: str) -> list[dict]:
    """Per-domain accuracy breakdown.

    Returns one row per domain (in display_order) plus an "Untagged" row if the
    user has any attempts on questions where `domain_id IS NULL`. v1 of the
    CLF-C02 dump has no domain tags, so expect a single Untagged bucket for now.
    """
    supabase = get_supabase()
    questions = (
        supabase.table("questions")
        .select("id, domain_id")
        .eq("certification_id", certification_id)
        .limit(10000)
        .execute()
    ).data or []
    q_to_domain = {q["id"]: q.get("domain_id") for q in questions}

    domains = (
        supabase.table("domains")
        .select("id, code, name, weight, display_order")
        .eq("certification_id", certification_id)
        .order("display_order")
        .execute()
    ).data or []

    stats = (
        supabase.table("question_stats")
        .select("question_id, times_seen, times_correct")
        .eq("user_id", user_id)
        .limit(10000)
        .execute()
    ).data or []

    bucket: dict = {}  # domain_id (or None) -> {attempts, correct}
    for s in stats:
        d_id = q_to_domain.get(s["question_id"])
        b = bucket.setdefault(d_id, {"attempts": 0, "correct": 0})
        b["attempts"] += s["times_seen"]
        b["correct"] += s["times_correct"]

    def _row(domain_id, code, name, weight) -> dict:
        b = bucket.get(domain_id, {"attempts": 0, "correct": 0})
        acc = (b["correct"] / b["attempts"] * 100) if b["attempts"] else None
        return {
            "domain_id": domain_id,
            "code": code,
            "name": name,
            "weight": float(weight) if weight is not None else 0.0,
            "attempts": b["attempts"],
            "correct": b["correct"],
            "accuracy_pct": round(acc, 1) if acc is not None else None,
        }

    rows = [_row(d["id"], d["code"], d["name"], d["weight"]) for d in domains]
    if None in bucket:
        rows.append(_row(None, "untagged", "Untagged", 0))
    return rows


# ---------------------------------------------------------------------------
# Flashcards (added post-MVP)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL_REFERENCE)
def list_flashcard_decks(certification_id: str) -> list[dict]:
    """Return all decks for a certification, ordered for display, with card counts."""
    supabase = get_supabase()
    decks = (
        supabase.table("flashcard_decks")
        .select("id, code, name, description, display_order")
        .eq("certification_id", certification_id)
        .order("display_order")
        .execute()
    ).data or []
    if not decks:
        return []
    deck_ids = [d["id"] for d in decks]
    counts = (
        supabase.table("flashcards")
        .select("deck_id", count="exact")
        .in_("deck_id", deck_ids)
        .eq("is_active", True)
        .execute()
    )
    # PostgREST returns total count across the filter, not per-deck. Fetch per-deck.
    # For small N (4-5 decks) a loop is fine.
    by_deck: dict[str, int] = {}
    for d_id in deck_ids:
        r = (
            supabase.table("flashcards")
            .select("id", count="exact")
            .eq("deck_id", d_id)
            .eq("is_active", True)
            .execute()
        )
        by_deck[d_id] = r.count or 0
    return [{**d, "card_count": by_deck[d["id"]]} for d in decks]


def get_deck_progress(user_id: str, deck_id: str) -> dict:
    """Return how many cards in this deck the user has reviewed / knows."""
    supabase = get_supabase()
    # All cards in the deck
    cards = (
        supabase.table("flashcards")
        .select("id")
        .eq("deck_id", deck_id)
        .eq("is_active", True)
        .limit(10000)
        .execute()
    ).data or []
    card_ids = {c["id"] for c in cards}
    if not card_ids:
        return {"total": 0, "reviewed": 0, "known": 0}
    # Stats this user has for these cards
    stats = (
        supabase.table("flashcard_stats")
        .select("flashcard_id, times_reviewed, times_correct, last_reviewed_at, last_correct_at")
        .eq("user_id", user_id)
        .limit(10000)
        .execute()
    ).data or []
    relevant = [s for s in stats if s["flashcard_id"] in card_ids]
    reviewed = len(relevant)
    # "Known" heuristic: last review was correct (last_correct_at >= last_reviewed_at)
    known = sum(
        1
        for s in relevant
        if s["last_correct_at"] and s["last_correct_at"] >= s["last_reviewed_at"]
    )
    return {"total": len(card_ids), "reviewed": reviewed, "known": known}


def pick_deck_card_ids(
    user_id: str,
    deck_id: str,
    mode: str = "all",
    count: int | None = None,
) -> list[str]:
    """Choose flashcards from a deck according to the user's study mode.

    `mode` values:
        all       -- every active card in the deck, shuffled.
        unseen    -- cards the user hasn't reviewed yet.
        practice  -- cards whose last review was wrong (or never reviewed).
    """
    supabase = get_supabase()
    cards = (
        supabase.table("flashcards")
        .select("id")
        .eq("deck_id", deck_id)
        .eq("is_active", True)
        .limit(10000)
        .execute()
    ).data or []
    all_ids = [c["id"] for c in cards]
    if not all_ids:
        return []

    if mode == "all":
        chosen = all_ids
    else:
        stats = (
            supabase.table("flashcard_stats")
            .select("flashcard_id, times_reviewed, last_reviewed_at, last_correct_at")
            .eq("user_id", user_id)
            .limit(10000)
            .execute()
        ).data or []
        stats_by_id = {s["flashcard_id"]: s for s in stats}
        if mode == "unseen":
            chosen = [cid for cid in all_ids if cid not in stats_by_id]
        elif mode == "practice":
            chosen = []
            for cid in all_ids:
                s = stats_by_id.get(cid)
                if s is None:
                    chosen.append(cid)  # never reviewed -> needs practice
                elif not s["last_correct_at"] or s["last_correct_at"] < s["last_reviewed_at"]:
                    chosen.append(cid)  # last attempt was wrong
        else:
            raise ValueError(f"Unknown flashcard mode: {mode}")

    random.shuffle(chosen)
    if count is not None:
        chosen = chosen[:count]
    return chosen


@st.cache_data(ttl=CACHE_TTL_QUESTION)
def get_flashcard(card_id: str) -> dict:
    supabase = get_supabase()
    return (
        supabase.table("flashcards")
        .select("id, deck_id, front, back, category")
        .eq("id", card_id)
        .single()
        .execute()
    ).data


def record_flashcard_review(user_id: str, card_id: str, knew_it: bool) -> None:
    supabase = get_supabase()
    supabase.table("flashcard_reviews").insert({
        "user_id": user_id,
        "flashcard_id": card_id,
        "knew_it": knew_it,
    }).execute()


@st.cache_data(ttl=CACHE_TTL_STATS)
def get_recent_answers(
    user_id: str,
    certification_id: str,
    limit: int = 1000,
) -> list[dict]:
    """Return the user's most recent (answered_at, is_correct) tuples for one cert.

    Scoped via exam_sessions.certification_id so practice + timed + review +
    bookmarked all contribute. Used by the stats page's practice-trend chart.
    """
    supabase = get_supabase()
    session_rows = (
        supabase.table("exam_sessions")
        .select("id")
        .eq("user_id", user_id)
        .eq("certification_id", certification_id)
        .limit(10000)
        .execute()
    ).data or []
    session_ids = [s["id"] for s in session_rows]
    if not session_ids:
        return []
    return (
        supabase.table("user_answers")
        .select("answered_at, is_correct")
        .in_("session_id", session_ids)
        .order("answered_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []


@st.cache_data(ttl=CACHE_TTL_STATS)
def get_practice_streak(user_id: str) -> int:
    """Consecutive UTC days with at least one session, ending today or yesterday.

    Returns 0 if the user hasn't practiced today AND not yesterday (broken streak).
    """
    supabase = get_supabase()
    rows = (
        supabase.table("exam_sessions")
        .select("started_at")
        .eq("user_id", user_id)
        .order("started_at", desc=True)
        .limit(2000)
        .execute()
    ).data or []
    if not rows:
        return 0
    dates = {
        datetime.fromisoformat(r["started_at"].replace("Z", "+00:00")).date()
        for r in rows
    }
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    if today not in dates and yesterday not in dates:
        return 0
    cursor = today if today in dates else yesterday
    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
