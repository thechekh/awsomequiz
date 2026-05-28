"""Business-logic tests for app/queries.py.

Tests pure logic (date arithmetic, formatting) and the new domain-weighted
allocation. Heavier mocking lives in test_session.py.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# format_started_at: ISO timestamp prettifier
# ---------------------------------------------------------------------------


def test_format_started_at_strips_microseconds_and_T() -> None:
    from app.queries import format_started_at
    assert format_started_at("2026-05-28T14:43:43.315096+00:00") == "2026-05-28 14:43:43"


def test_format_started_at_none() -> None:
    from app.queries import format_started_at
    assert format_started_at(None) == "--"


def test_format_started_at_already_short() -> None:
    from app.queries import format_started_at
    # 19-char prefix is the cut-off; anything shorter is returned as-is.
    assert format_started_at("2026-05-28T14:43:43") == "2026-05-28 14:43:43"


# ---------------------------------------------------------------------------
# get_practice_streak: date-only counting from session start timestamps
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _mock_supabase_for_sessions(session_dates: list[datetime]):
    """Build a Supabase mock that returns the given session start_at values."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(
        data=[{"started_at": _iso(d)} for d in session_dates]
    )
    client = MagicMock()
    client.table.return_value = chain
    return client


@pytest.fixture
def fixed_now(monkeypatch):
    """Pin `datetime.now(timezone.utc)` so streak tests are deterministic."""
    # Reference instant: 2026-05-28 12:00 UTC (Thursday).
    fixed = datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)
    yield fixed


def test_streak_zero_when_no_sessions() -> None:
    from app.queries import get_practice_streak
    with patch("app.queries.get_supabase", return_value=_mock_supabase_for_sessions([])):
        get_practice_streak.clear()  # bust @st.cache_data
        assert get_practice_streak("u1") == 0


def test_streak_zero_when_last_session_is_three_days_ago(fixed_now) -> None:
    from app.queries import get_practice_streak
    # No session today / yesterday -> streak broken.
    dates = [fixed_now - timedelta(days=3)]
    with patch("app.queries.get_supabase", return_value=_mock_supabase_for_sessions(dates)), \
         patch("app.queries.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat = datetime.fromisoformat
        get_practice_streak.clear()
        assert get_practice_streak("u1") == 0


def test_streak_counts_consecutive_days_ending_today(fixed_now) -> None:
    from app.queries import get_practice_streak
    dates = [fixed_now - timedelta(days=i) for i in range(5)]   # today + 4 prior
    with patch("app.queries.get_supabase", return_value=_mock_supabase_for_sessions(dates)), \
         patch("app.queries.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat = datetime.fromisoformat
        get_practice_streak.clear()
        assert get_practice_streak("u1") == 5


def test_streak_grace_period_yesterday_only(fixed_now) -> None:
    from app.queries import get_practice_streak
    # Practiced yesterday but not today -> still counted.
    dates = [fixed_now - timedelta(days=1)]
    with patch("app.queries.get_supabase", return_value=_mock_supabase_for_sessions(dates)), \
         patch("app.queries.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat = datetime.fromisoformat
        get_practice_streak.clear()
        assert get_practice_streak("u1") == 1


def test_streak_breaks_on_gap(fixed_now) -> None:
    from app.queries import get_practice_streak
    # Sessions on days 0, 1, 2, then a gap of 2 days, then days 5, 6.
    # Streak from today should be 3 (today/yesterday/2-days-ago) and stop at the gap.
    dates = [
        fixed_now - timedelta(days=0),
        fixed_now - timedelta(days=1),
        fixed_now - timedelta(days=2),
        fixed_now - timedelta(days=5),
        fixed_now - timedelta(days=6),
    ]
    with patch("app.queries.get_supabase", return_value=_mock_supabase_for_sessions(dates)), \
         patch("app.queries.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.fromisoformat = datetime.fromisoformat
        get_practice_streak.clear()
        assert get_practice_streak("u1") == 3


# ---------------------------------------------------------------------------
# REPORT_REASONS: schema check (catches typos in pages that hardcode them)
# ---------------------------------------------------------------------------


def test_report_reasons_set() -> None:
    from app.queries import REPORT_REASONS
    assert set(REPORT_REASONS) == {
        "incorrect_answer", "typo", "ambiguous", "outdated", "other"
    }
