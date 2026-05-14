from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catop.models import CacheEvent


def event_from_litellm_record(
    record: dict[str, Any],
    *,
    default_agent: str = "jsonl",
    default_project: str = "-",
    default_session: str = "-",
    claude_usage_semantics: bool = False,
) -> CacheEvent:
    usage = _first_dict(
        record.get("usage"),
        _nested(record, "message", "usage"),
        _nested(record, "payload", "info", "last_token_usage"),
        _nested(record, "response", "usage"),
        _nested(record, "raw_response", "usage"),
        _nested(record, "litellm_response", "usage"),
    )
    input_details = _first_dict(
        usage.get("prompt_tokens_details"),
        usage.get("input_tokens_details"),
        _nested(record, "response", "usage", "prompt_tokens_details"),
    )
    output_details = _first_dict(
        usage.get("completion_tokens_details"),
        usage.get("output_tokens_details"),
        _nested(record, "response", "usage", "completion_tokens_details"),
    )
    metadata = _first_dict(record.get("metadata"), record.get("litellm_metadata"))
    attributes = _first_dict(record.get("attributes"), _nested(record, "payload", "attributes"))

    agent = str(
        _coalesce(
            record.get("agent"),
            record.get("client"),
            record.get("source"),
            metadata.get("agent"),
            metadata.get("client"),
            default_agent,
        )
    )
    model = str(
        _coalesce(
            record.get("model"),
            record.get("model_name"),
            record.get("model_id"),
            usage.get("model"),
            attributes.get("gen_ai.response.model"),
            _nested(record, "message", "model"),
            _nested(record, "response", "model"),
            "unknown",
        )
    )
    provider = str(
        _coalesce(
            record.get("provider"),
            record.get("litellm_provider"),
            record.get("custom_llm_provider"),
            usage.get("provider"),
            attributes.get("gen_ai.system"),
            metadata.get("litellm_provider"),
            _provider_from_model(model),
            "unknown",
        )
    )
    project = str(
        _coalesce(
            record.get("project"),
            record.get("project_id"),
            record.get("team_id"),
            record.get("user"),
            metadata.get("project"),
            metadata.get("team_id"),
            metadata.get("user_api_key_alias"),
            default_project,
        )
    )
    session_id = str(
        _coalesce(
            record.get("session_id"),
            record.get("session"),
            record.get("conversation_id"),
            record.get("thread_id"),
            metadata.get("session_id"),
            metadata.get("session"),
            metadata.get("conversation_id"),
            metadata.get("thread_id"),
            metadata.get("trace_id"),
            record.get("id"),
            default_session,
        )
    )

    raw_input_tokens = _to_int(
        _coalesce(
            usage.get("prompt_tokens"),
            usage.get("input_tokens"),
            usage.get("input"),
            usage.get("tokensIn"),
            attributes.get("gen_ai.usage.input_tokens"),
            record.get("prompt_tokens"),
            record.get("input_tokens"),
            0,
        )
    )
    cached_tokens = _to_int(
        _coalesce(
            input_details.get("cached_tokens"),
            input_details.get("cache_read_input_tokens"),
            usage.get("cache_read_input_tokens"),
            usage.get("input_cache_read"),
            usage.get("cacheRead"),
            usage.get("cacheReads"),
            usage.get("cached"),
            usage.get("cached_tokens"),
            usage.get("cached_input_tokens"),
            usage.get("input_cached_tokens"),
            usage.get("prompt_cache_hit_tokens"),
            attributes.get("gen_ai.usage.cache_read.input_tokens"),
            record.get("cache_read_input_tokens"),
            record.get("cached_tokens"),
            record.get("cache_hit_tokens"),
            0,
        )
    )
    cache_creation_tokens = _to_int(
        _coalesce(
            input_details.get("cache_creation_tokens"),
            input_details.get("cache_creation_input_tokens"),
            usage.get("cache_creation_input_tokens"),
            usage.get("input_cache_creation"),
            usage.get("cacheCreate"),
            usage.get("cacheWrite"),
            usage.get("cacheWrites"),
            attributes.get("gen_ai.usage.cache_creation.input_tokens"),
            record.get("cache_creation_input_tokens"),
            record.get("cache_write_input_tokens"),
            0,
        )
    )
    output_tokens = _to_int(
        _coalesce(
            usage.get("completion_tokens"),
            usage.get("output_tokens"),
            usage.get("output"),
            usage.get("tokensOut"),
            usage.get("candidatesTokenCount"),
            attributes.get("gen_ai.usage.output_tokens"),
            record.get("completion_tokens"),
            record.get("output_tokens"),
            0,
        )
    )
    reasoning_tokens = _to_int(
        _coalesce(
            output_details.get("reasoning_tokens"),
            output_details.get("reasoning_output_tokens"),
            input_details.get("reasoning_tokens"),
            input_details.get("reasoning_output_tokens"),
            usage.get("reasoning_tokens"),
            usage.get("reasoning_output_tokens"),
            usage.get("thoughtsTokenCount"),
            usage.get("thoughts"),
            attributes.get("gen_ai.usage.reasoning.output_tokens"),
            record.get("reasoning_tokens"),
            0,
        )
    )

    input_tokens = raw_input_tokens
    if claude_usage_semantics and (cached_tokens or cache_creation_tokens):
        input_tokens = raw_input_tokens + cached_tokens + cache_creation_tokens
    else:
        input_tokens = max(input_tokens, cached_tokens + cache_creation_tokens)

    actual_cost_usd = _to_optional_float(
        _coalesce(
            record.get("response_cost"),
            record.get("cost"),
            record.get("spend"),
            record.get("total_cost"),
            _nested(usage, "cost", "total"),
            _nested(record, "response", "_hidden_params", "response_cost"),
            metadata.get("response_cost"),
        )
    )
    timestamp = _parse_timestamp(
        _coalesce(
            record.get("timestamp"),
            record.get("created_at"),
            record.get("startTime"),
            record.get("start_time"),
            record.get("created"),
            _nested(record, "message", "timestamp"),
            _nested(record, "payload", "timestamp"),
        )
    )

    return CacheEvent(
        timestamp=timestamp,
        agent=agent,
        provider=provider,
        model=model,
        project=project,
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        reasoning_tokens=reasoning_tokens,
        actual_cost_usd=actual_cost_usd,
        session_id=session_id,
    )


def read_jsonl_events(path: Path) -> list[CacheEvent]:
    with path.open("r", encoding="utf-8") as handle:
        return list(events_from_jsonl(handle))


def read_stdin_events() -> list[CacheEvent]:
    return list(events_from_jsonl(sys.stdin))


def events_from_jsonl(
    lines: Iterable[str],
    *,
    default_agent: str = "jsonl",
    default_project: str = "-",
    default_session: str = "-",
    claude_usage_semantics: bool = False,
) -> Iterator[CacheEvent]:
    for line in lines:
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        record = _loads_json_object(stripped)
        if record is None:
            continue
        if isinstance(record, dict):
            event = event_from_litellm_record(
                record,
                default_agent=default_agent,
                default_project=default_project,
                default_session=default_session,
                claude_usage_semantics=claude_usage_semantics,
            )
            if event.has_usage:
                yield event


def _nested(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _loads_json_object(value: str) -> Any | None:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        try:
            repaired = value.encode("cp936").decode("utf-8-sig")
            return json.loads(repaired)
        except (UnicodeError, json.JSONDecodeError):
            return None


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _to_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _provider_from_model(model: str) -> str | None:
    if "/" in model:
        return model.split("/", 1)[0]
    if model.startswith("gpt-") or "codex" in model:
        return "openai"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gemini-"):
        return "google"
    if model.startswith("deepseek-"):
        return "deepseek"
    return None
