from __future__ import annotations

from datetime import datetime, timezone

import pytest

from catop.models import CacheEvent
from catop.pricing import PriceCatalog
from catop.stats import aggregate_events, parse_group_by, summarize_events


def test_summarize_and_group_events() -> None:
    catalog = PriceCatalog.from_raw(
        {
            "gpt-4o": {
                "litellm_provider": "openai",
                "input_cost_per_token": 2.0e-6,
                "cache_read_input_token_cost": 1.0e-6,
            }
        },
        source="test",
    )
    events = [
        CacheEvent(
            timestamp=datetime.now(timezone.utc),
            provider="openai",
            model="gpt-4o",
            project="alpha",
            input_tokens=1000,
            cached_tokens=700,
            actual_cost_usd=0.01,
        ),
        CacheEvent(
            timestamp=datetime.now(timezone.utc),
            provider="openai",
            model="gpt-4o",
            project="alpha",
            input_tokens=500,
            cached_tokens=100,
        ),
    ]

    summary = summarize_events(events, catalog)
    rows = aggregate_events(events, catalog, group_by=("provider", "model", "project"))

    assert summary.request_count == 2
    assert summary.cached_tokens == 800
    assert round(summary.hit_rate, 4) == round(800 / 1500, 4)
    assert summary.saved_usd == pytest.approx(0.0008)
    assert summary.actual_cost_usd == 0.01
    assert len(rows) == 1
    assert rows[0].project == "alpha"


def test_parse_group_by_rejects_unknown_fields() -> None:
    try:
        parse_group_by("provider,team")
    except ValueError as exc:
        assert "team" in str(exc)
    else:
        raise AssertionError("expected ValueError")
