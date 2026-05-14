from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from catop.models import CacheEvent
from catop.pricing import PriceCatalog

VALID_GROUP_FIELDS = ("agent", "provider", "model", "project", "session")


@dataclass
class MetricsRow:
    agent: str
    provider: str
    model: str
    project: str
    session_id: str
    request_count: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    cache_creation_tokens: int = 0
    miss_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    saved_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    actual_cost_usd: float = 0.0

    @property
    def hit_rate(self) -> float:
        if self.input_tokens <= 0:
            return 0.0
        return min(self.cached_tokens / self.input_tokens, 1.0)

    @property
    def cache_write_rate(self) -> float:
        if self.input_tokens <= 0:
            return 0.0
        return min(self.cache_creation_tokens / self.input_tokens, 1.0)


@dataclass(frozen=True)
class Summary:
    request_count: int
    input_tokens: int
    cached_tokens: int
    cache_creation_tokens: int
    miss_tokens: int
    output_tokens: int
    reasoning_tokens: int
    hit_rate: float
    cache_write_rate: float
    saved_usd: float
    estimated_cost_usd: float
    actual_cost_usd: float


def aggregate_events(
    events: Iterable[CacheEvent],
    catalog: PriceCatalog,
    group_by: tuple[str, ...] = VALID_GROUP_FIELDS,
) -> list[MetricsRow]:
    rows: dict[tuple[str, ...], MetricsRow] = {}
    for event in events:
        key = tuple(_field_value(event, field) for field in group_by)
        if key not in rows:
            rows[key] = MetricsRow(
                agent=event.agent if "agent" in group_by else "*",
                provider=event.provider if "provider" in group_by else "*",
                model=event.model if "model" in group_by else "*",
                project=event.project if "project" in group_by else "*",
                session_id=event.session_id if "session" in group_by else "*",
            )
        row = rows[key]
        row.request_count += 1
        row.input_tokens += event.input_tokens
        row.cached_tokens += event.cached_tokens
        row.cache_creation_tokens += event.cache_creation_tokens
        row.miss_tokens += event.miss_tokens
        row.output_tokens += event.output_tokens
        row.reasoning_tokens += event.reasoning_tokens
        row.saved_usd += catalog.estimate_saved_usd(
            event.model,
            event.input_tokens,
            event.cached_tokens,
            cache_creation_tokens=event.cache_creation_tokens,
            output_tokens=event.output_tokens,
            reasoning_tokens=event.reasoning_tokens,
            provider=event.provider,
        )
        row.estimated_cost_usd += catalog.estimate_cached_cost_usd(
            event.model,
            event.input_tokens,
            event.cached_tokens,
            cache_creation_tokens=event.cache_creation_tokens,
            output_tokens=event.output_tokens,
            reasoning_tokens=event.reasoning_tokens,
            provider=event.provider,
        )
        if event.actual_cost_usd is not None:
            row.actual_cost_usd += event.actual_cost_usd
    return sorted(rows.values(), key=lambda row: row.saved_usd, reverse=True)


def summarize_events(events: Iterable[CacheEvent], catalog: PriceCatalog) -> Summary:
    rows = aggregate_events(events, catalog)
    input_tokens = sum(row.input_tokens for row in rows)
    cached_tokens = sum(row.cached_tokens for row in rows)
    cache_creation_tokens = sum(row.cache_creation_tokens for row in rows)
    miss_tokens = sum(row.miss_tokens for row in rows)
    hit_rate = cached_tokens / input_tokens if input_tokens else 0.0
    cache_write_rate = cache_creation_tokens / input_tokens if input_tokens else 0.0
    return Summary(
        request_count=sum(row.request_count for row in rows),
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        cache_creation_tokens=cache_creation_tokens,
        miss_tokens=miss_tokens,
        output_tokens=sum(row.output_tokens for row in rows),
        reasoning_tokens=sum(row.reasoning_tokens for row in rows),
        hit_rate=hit_rate,
        cache_write_rate=cache_write_rate,
        saved_usd=sum(row.saved_usd for row in rows),
        estimated_cost_usd=sum(row.estimated_cost_usd for row in rows),
        actual_cost_usd=sum(row.actual_cost_usd for row in rows),
    )


def parse_group_by(value: str) -> tuple[str, ...]:
    fields = tuple(part.strip() for part in value.split(",") if part.strip())
    invalid = [field for field in fields if field not in VALID_GROUP_FIELDS]
    if invalid:
        valid = ", ".join(VALID_GROUP_FIELDS)
        raise ValueError(f"Invalid group field(s): {', '.join(invalid)}. Valid fields: {valid}.")
    return fields or VALID_GROUP_FIELDS


def _field_value(event: CacheEvent, field: str) -> str:
    if field == "session":
        return event.session_id
    return str(getattr(event, field))
