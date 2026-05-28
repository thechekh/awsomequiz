"""Business-logic tests for app/session.py.

We mock `app.db.get_supabase` so we don't need a running Supabase. The tests
exercise the answer-correctness math, completion scoring, and the new
domain-weighted question allocation used by the timed exam.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# _allocate_per_domain (pure math; no mocks needed)
# ---------------------------------------------------------------------------


def test_allocate_clfc02_official_split() -> None:
    from app.session import _allocate_per_domain
    # CLF-C02: 24/30/34/12 % over 65 questions -> ~16/19/22/8 (sums to 65).
    result = _allocate_per_domain(65, [24, 30, 34, 12])
    assert sum(result) == 65
    # Each domain rounds to within 1 of the expected proportion.
    expected = [15.6, 19.5, 22.1, 7.8]
    for got, exp in zip(result, expected):
        assert abs(got - exp) <= 1


def test_allocate_dvac02_official_split() -> None:
    from app.session import _allocate_per_domain
    # DVA-C02: 32/26/24/18 % over 65 questions.
    result = _allocate_per_domain(65, [32, 26, 24, 18])
    assert sum(result) == 65


def test_allocate_zero_weights_returns_empty() -> None:
    from app.session import _allocate_per_domain
    assert _allocate_per_domain(65, []) == []
    assert _allocate_per_domain(65, [0, 0, 0]) == []


def test_allocate_uneven_remainder_distributed_to_largest_fractions() -> None:
    from app.session import _allocate_per_domain
    # 10 items, 3 equal weights -> 3+3+3 = 9, remainder 1 goes to first.
    result = _allocate_per_domain(10, [1, 1, 1])
    assert sum(result) == 10
    assert max(result) - min(result) <= 1


def test_allocate_handles_single_domain() -> None:
    from app.session import _allocate_per_domain
    result = _allocate_per_domain(65, [100])
    assert result == [65]


# ---------------------------------------------------------------------------
# record_answer correctness logic
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_supabase():
    """Mock the Supabase client; record .upsert() / .insert() / .select() calls."""
    with patch("app.session.get_supabase") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


def test_record_answer_returns_true_when_selection_matches(mock_supabase) -> None:
    from app.session import record_answer
    result = record_answer(
        session_id="s1",
        question_id="q1",
        selected_option_ids=["o2", "o3"],
        correct_option_ids=["o3", "o2"],   # same set, different order
        time_spent_seconds=10,
    )
    assert result is True


def test_record_answer_returns_false_on_mismatch(mock_supabase) -> None:
    from app.session import record_answer
    assert record_answer("s1", "q1", ["o1"], ["o2"], 5) is False


def test_record_answer_returns_false_on_partial_multi(mock_supabase) -> None:
    from app.session import record_answer
    assert record_answer("s1", "q1", ["o1"], ["o1", "o2"], 5) is False


def test_record_answer_calls_upsert_with_correct_keys(mock_supabase) -> None:
    from app.session import record_answer
    record_answer("s1", "q1", ["o1"], ["o1"], 7)
    upsert_call = mock_supabase.table.return_value.upsert
    assert upsert_call.called
    payload = upsert_call.call_args.args[0]
    assert payload["session_id"] == "s1"
    assert payload["question_id"] == "q1"
    assert payload["selected_option_ids"] == ["o1"]
    assert payload["is_correct"] is True
    assert payload["time_spent_seconds"] == 7
    assert "answered_at" in payload


# ---------------------------------------------------------------------------
# complete_session scoring
# ---------------------------------------------------------------------------


def test_complete_session_scores_unanswered_as_wrong(mock_supabase) -> None:
    """65-question exam, 50 answered, 35 correct -> 35/65 = 53.85% (below 70% pass)."""
    from app.session import complete_session

    # Mock chain: user_answers -> 50 answer rows (35 correct)
    answers_data = [{"is_correct": i < 35} for i in range(50)]
    sess_data = {
        "certification_id": "cert-clf",
        "started_at": "2026-05-28T10:00:00+00:00",
        "question_count": 65,
    }
    cert_data = {"pass_threshold_pct": 70}

    # Build per-call mock chains
    table_mock = mock_supabase.table
    table_mock.side_effect = lambda name: _build_table_mock(
        name, answers_data, sess_data, cert_data
    )

    summary = complete_session("sess-1")
    assert summary["total"] == 65
    assert summary["correct"] == 35
    assert summary["score_pct"] == 53.85
    assert summary["passed"] is False


def test_complete_session_passes_above_threshold(mock_supabase) -> None:
    from app.session import complete_session

    answers_data = [{"is_correct": True}] * 50 + [{"is_correct": False}] * 15
    sess_data = {
        "certification_id": "cert-clf",
        "started_at": "2026-05-28T10:00:00+00:00",
        "question_count": 65,
    }
    cert_data = {"pass_threshold_pct": 70}

    mock_supabase.table.side_effect = lambda name: _build_table_mock(
        name, answers_data, sess_data, cert_data
    )

    summary = complete_session("sess-1")
    assert summary["correct"] == 50
    assert summary["score_pct"] == 76.92
    assert summary["passed"] is True


def _build_table_mock(name, answers_data, sess_data, cert_data):
    """Build a chained mock for one of: user_answers / exam_sessions / certifications."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.single.return_value = chain
    chain.update.return_value = chain
    chain.insert.return_value = chain
    chain.upsert.return_value = chain
    if name == "user_answers":
        chain.execute.return_value = MagicMock(data=answers_data)
    elif name == "exam_sessions":
        chain.execute.return_value = MagicMock(data=sess_data)
    elif name == "certifications":
        chain.execute.return_value = MagicMock(data=cert_data)
    else:
        chain.execute.return_value = MagicMock(data=None)
    return chain
