from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from catop.models import CacheEvent

DEMO_MODELS = [
    ("openai", "gpt-4o"),
    ("openai", "gpt-4o-mini"),
    ("anthropic", "claude-sonnet-4-5"),
    ("deepseek", "deepseek-chat"),
    ("deepseek", "deepseek-reasoner"),
]
DEMO_PROJECTS = ["agent-loop", "rag-api", "eval-runner", "chatops"]


def generate_demo_event(rng: random.Random | None = None) -> CacheEvent:
    rng = rng or random.Random()
    provider, model = rng.choice(DEMO_MODELS)
    input_tokens = rng.randint(500, 12000)
    hit_rate = min(max(rng.betavariate(5, 2), 0.0), 1.0)
    cached_tokens = int(input_tokens * hit_rate)
    return CacheEvent(
        timestamp=datetime.now(timezone.utc),
        provider=provider,
        model=model,
        project=rng.choice(DEMO_PROJECTS),
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=rng.randint(80, 1800),
    )


def generate_demo_events(count: int = 15, seed: int | None = None) -> list[CacheEvent]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    events = []
    for index in range(count):
        event = generate_demo_event(rng)
        timestamp = now - timedelta(seconds=(count - index) * rng.uniform(5.0, 30.0))
        events.append(
            CacheEvent(
                timestamp=timestamp,
                provider=event.provider,
                model=event.model,
                project=event.project,
                input_tokens=event.input_tokens,
                cached_tokens=event.cached_tokens,
                output_tokens=event.output_tokens,
            )
        )
    return events
