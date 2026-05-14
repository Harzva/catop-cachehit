from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from catop.models import CacheEvent

WINDOW_CHOICES = ("all", "today", "week", "month")


def filter_events_by_window(
    events: Iterable[CacheEvent],
    window: str,
    *,
    now: datetime | None = None,
) -> list[CacheEvent]:
    if window == "all":
        return list(events)
    start = window_start(window, now=now)
    return [event for event in events if event.timestamp.astimezone() >= start]


def window_start(window: str, *, now: datetime | None = None) -> datetime:
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    if window == "today":
        return current.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "week":
        today_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start - timedelta(days=today_start.weekday())
    if window == "month":
        return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    valid = ", ".join(WINDOW_CHOICES)
    raise ValueError(f"Invalid time window: {window}. Valid windows: {valid}.")
