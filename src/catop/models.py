from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class CacheEvent:
    """One observed LLM request with enough token data to calculate cache value."""

    timestamp: datetime
    provider: str
    model: str
    project: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    actual_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))
        object.__setattr__(self, "input_tokens", max(0, int(self.input_tokens)))
        object.__setattr__(self, "cached_tokens", max(0, int(self.cached_tokens)))
        object.__setattr__(self, "output_tokens", max(0, int(self.output_tokens)))
        object.__setattr__(self, "cache_creation_tokens", max(0, int(self.cache_creation_tokens)))

    @property
    def miss_tokens(self) -> int:
        return max(self.input_tokens - self.cached_tokens, 0)

    @property
    def hit_rate(self) -> float:
        if self.input_tokens <= 0:
            return 0.0
        return min(self.cached_tokens / self.input_tokens, 1.0)
