from __future__ import annotations

from datetime import datetime, timezone

from catop.models import CacheEvent
from catop.time_windows import filter_events_by_window, window_start


def _event(timestamp: datetime) -> CacheEvent:
    return CacheEvent(
        timestamp=timestamp,
        agent="jsonl",
        provider="openai",
        model="gpt-4o",
        project="repo",
        input_tokens=100,
        cached_tokens=50,
    )


def test_calendar_windows_use_local_boundaries() -> None:
    now = datetime(2026, 5, 14, 9, 30, tzinfo=timezone.utc)

    assert window_start("today", now=now).day == 14
    assert window_start("week", now=now).day == 11
    assert window_start("month", now=now).day == 1


def test_filter_events_by_window() -> None:
    events = [
        _event(datetime(2026, 5, 13, 15, 59, tzinfo=timezone.utc)),
        _event(datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc)),
    ]

    filtered = filter_events_by_window(
        events,
        "today",
        now=datetime(2026, 5, 14, 9, 30, tzinfo=timezone.utc),
    )

    assert filtered == events[1:]
