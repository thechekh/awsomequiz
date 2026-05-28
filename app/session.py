"""Practice / exam session lifecycle.

A session row in `public.exam_sessions` carries the pre-picked sequence in
`question_ids`. Answers go into `public.user_answers` via UPSERT (so the
timed-exam runner can revise an answer before submitting). The
`user_answers_update_stats` DB trigger maintains `question_stats` on both
INSERT and UPDATE -- do NOT update the rollup here.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Literal

from app.db import get_supabase
from app.queries import (
    list_domains,
    pick_bookmarked_question_ids,
    pick_missed_question_ids,
    pick_question_ids,
    pick_weak_area_question_ids,
)

Mode = Literal["practice", "timed", "weak_areas", "missed", "domain_focus", "bookmarked"]


def _now_iso() -> str:
    """ISO-8601 UTC timestamp for the `completed_at` / `answered_at` columns."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------


def _create_session_row(
    user_id: str,
    certification_id: str,
    mode: Mode,
    question_ids: list[str],
    domain_ids: list[str] | None = None,
) -> dict:
    """Insert one exam_sessions row. Raises if no questions were picked."""
    if not question_ids:
        raise ValueError("No questions available for this mode/filter.")
    supabase = get_supabase()
    return (
        supabase.table("exam_sessions")
        .insert({
            "user_id": user_id,
            "certification_id": certification_id,
            "mode": mode,
            "domain_filter": domain_ids,
            "question_count": len(question_ids),
            "question_ids": question_ids,
        })
        .execute()
    ).data[0]


def start_practice_session(
    user_id: str,
    certification_id: str,
    count: int | None,
    domain_ids: list[str] | None = None,
    shuffle: bool = True,
) -> dict:
    """Create a practice session.

    shuffle=True (default): random order. shuffle=False: questions in their
    natural source order (by external_id) -- lets the user work through the
    whole set sequentially.
    """
    qids = pick_question_ids(certification_id, count, domain_ids, shuffle=shuffle)
    return _create_session_row(user_id, certification_id, "practice", qids, domain_ids)


def _allocate_per_domain(count: int, weights: list[float]) -> list[int]:
    """Largest-remainder method: split `count` items by float `weights`.

    Returns a list of integer counts (same length as `weights`) that sums to
    `count` exactly. Used so a 65-question CLF-C02 timed exam draws ~16/19/22/8
    from its four official domains (24/30/34/12 %) rather than uniformly.
    """
    if not weights or sum(weights) <= 0:
        return []
    total_weight = sum(weights)
    raw = [count * (w / total_weight) for w in weights]
    floored = [int(r) for r in raw]
    remainder = count - sum(floored)
    # Distribute the remainder to the largest fractional parts.
    fractional = sorted(
        range(len(weights)), key=lambda i: raw[i] - floored[i], reverse=True
    )
    for i in fractional[:remainder]:
        floored[i] += 1
    return floored


def start_timed_session(user_id: str, certification_id: str) -> dict:
    """Create a timed exam session.

    Question count + duration come from the `certifications` row (CLF-C02:
    65 questions / 90 minutes). When the cert has domains with weights set,
    questions are drawn proportionally per domain (CLF-C02: 24/30/34/12 %)
    so the simulation matches the real exam blueprint instead of being a
    uniform sample over all questions.
    """
    supabase = get_supabase()
    cert = (
        supabase.table("certifications")
        .select("question_count, duration_minutes")
        .eq("id", certification_id)
        .single()
        .execute()
    ).data
    count = cert["question_count"]

    qids = _pick_domain_weighted_qids(certification_id, count)
    if len(qids) < count:
        raise ValueError(
            f"Only {len(qids)} active questions available; need {count} for a timed exam."
        )
    return _create_session_row(user_id, certification_id, "timed", qids)


def _pick_domain_weighted_qids(certification_id: str, count: int) -> list[str]:
    """Pick `count` question IDs respecting the cert's domain weights.

    Falls back to uniform random sampling when no domain has a weight, or
    when domain-weighted picking can't fill the request (small domains).
    """
    domains = list_domains(certification_id)
    weighted = [d for d in domains if d.get("weight") and float(d["weight"]) > 0]
    if not weighted or len(weighted) < 2:
        return pick_question_ids(certification_id, count)

    weights = [float(d["weight"]) for d in weighted]
    targets = _allocate_per_domain(count, weights)

    qids: list[str] = []
    shortfall_domains: list[int] = []
    for i, (domain, target) in enumerate(zip(weighted, targets)):
        if target <= 0:
            continue
        picked = pick_question_ids(certification_id, target, domain_ids=[domain["id"]])
        qids.extend(picked)
        if len(picked) < target:
            shortfall_domains.append(target - len(picked))

    # If any domain ran out of questions, top up from the global pool
    # (untagged + other domains' overflow), avoiding duplicates.
    if len(qids) < count:
        seen = set(qids)
        all_qids = pick_question_ids(certification_id, None)
        for qid in all_qids:
            if qid not in seen:
                qids.append(qid)
                seen.add(qid)
                if len(qids) >= count:
                    break

    random.shuffle(qids)
    return qids[:count]


def start_weak_areas_session(
    user_id: str,
    certification_id: str,
    count: int | None,
    threshold_pct: int = 70,
    min_attempts: int = 3,
) -> dict:
    """Start a session of weak-area questions (low accuracy or unseen)."""
    qids = pick_weak_area_question_ids(
        user_id, certification_id, count, threshold_pct, min_attempts
    )
    return _create_session_row(user_id, certification_id, "weak_areas", qids)


def start_missed_session(
    user_id: str,
    certification_id: str,
    count: int | None,
) -> dict:
    """Start a session of questions the user has gotten wrong previously."""
    qids = pick_missed_question_ids(user_id, certification_id, count)
    return _create_session_row(user_id, certification_id, "missed", qids)


def start_bookmarked_session(
    user_id: str,
    certification_id: str,
    count: int | None,
) -> dict:
    """Start a session of the user's bookmarked questions."""
    qids = pick_bookmarked_question_ids(user_id, certification_id, count)
    return _create_session_row(user_id, certification_id, "bookmarked", qids)


# ---------------------------------------------------------------------------
# Session lookup
# ---------------------------------------------------------------------------


def get_active_session_by_mode(user_id: str, mode: Mode) -> dict | None:
    """Return the user's most-recent incomplete session of the given mode, if any."""
    supabase = get_supabase()
    rows = (
        supabase.table("exam_sessions")
        .select("id, started_at, question_count, question_ids, domain_filter, certification_id, mode")
        .eq("user_id", user_id)
        .eq("mode", mode)
        .is_("completed_at", "null")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def get_active_practice_session(user_id: str) -> dict | None:
    return get_active_session_by_mode(user_id, "practice")


def get_active_timed_session(user_id: str) -> dict | None:
    return get_active_session_by_mode(user_id, "timed")


def get_active_review_session(user_id: str) -> dict | None:
    """Return the most-recent incomplete weak/missed session, or None.

    review.py shares state across its three tabs; only one weak-or-missed
    session can be in flight at a time. Bookmarked sessions live on
    bookmarks.py (separate state) and are excluded here.
    """
    supabase = get_supabase()
    rows = (
        supabase.table("exam_sessions")
        .select("id, started_at, question_count, question_ids, certification_id, mode")
        .eq("user_id", user_id)
        .in_("mode", ["weak_areas", "missed"])
        .is_("completed_at", "null")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def get_active_bookmarked_session(user_id: str) -> dict | None:
    return get_active_session_by_mode(user_id, "bookmarked")


# ---------------------------------------------------------------------------
# Answering
# ---------------------------------------------------------------------------


def record_answer(
    session_id: str,
    question_id: str,
    selected_option_ids: list[str],
    correct_option_ids: list[str],
    time_spent_seconds: int,
) -> bool:
    """Upsert one user_answers row. Returns is_correct.

    UPSERT (not INSERT) so timed-mode revisions don't violate the PK. The
    `user_answers_update_stats` trigger reacts to both INSERT and UPDATE,
    so question_stats stays accurate either way.
    """
    is_correct = sorted(selected_option_ids) == sorted(correct_option_ids)
    supabase = get_supabase()
    (
        supabase.table("user_answers")
        .upsert({
            "session_id": session_id,
            "question_id": question_id,
            "selected_option_ids": selected_option_ids,
            "is_correct": is_correct,
            "time_spent_seconds": time_spent_seconds,
            "answered_at": _now_iso(),
        }, on_conflict="session_id,question_id")
        .execute()
    )
    return is_correct


# ---------------------------------------------------------------------------
# Session completion
# ---------------------------------------------------------------------------


def complete_session(session_id: str) -> dict:
    """Stamp the session as complete and compute final score / pass."""
    supabase = get_supabase()
    answers = (
        supabase.table("user_answers")
        .select("is_correct")
        .eq("session_id", session_id)
        .execute()
    ).data or []
    sess = (
        supabase.table("exam_sessions")
        .select("certification_id, started_at, question_count")
        .eq("id", session_id)
        .single()
        .execute()
    ).data
    # Unanswered questions count as wrong (matches real exam scoring).
    total = sess["question_count"]
    correct = sum(1 for a in answers if a["is_correct"])
    score_pct = round((correct / total * 100), 2) if total else 0.0

    cert = (
        supabase.table("certifications")
        .select("pass_threshold_pct")
        .eq("id", sess["certification_id"])
        .single()
        .execute()
    ).data
    passed = score_pct >= cert["pass_threshold_pct"]

    started_at = datetime.fromisoformat(sess["started_at"].replace("Z", "+00:00"))
    duration_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())

    (
        supabase.table("exam_sessions")
        .update({
            "completed_at": _now_iso(),
            "duration_seconds": duration_seconds,
            "score_pct": score_pct,
            "passed": passed,
        })
        .eq("id", session_id)
        .execute()
    )
    return {
        "session_id": session_id,
        "total": total,
        "answered": len(answers),
        "correct": correct,
        "score_pct": score_pct,
        "passed": passed,
        "duration_seconds": duration_seconds,
    }


def abandon_session(session_id: str) -> None:
    """Mark a session as ended without scoring (user cancelled)."""
    supabase = get_supabase()
    (
        supabase.table("exam_sessions")
        .update({"completed_at": _now_iso()})
        .eq("id", session_id)
        .execute()
    )
