from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # pragma: no cover - LiteLLM is optional for the catop CLI test environment.
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:  # pragma: no cover
    class CustomLogger:  # type: ignore[no-redef]
        pass


DEFAULT_PROXY_LOG_NAME = "litellm-proxy-cachehit.jsonl"


class CatopLiteLLMProxyLogger(CustomLogger):
    """LiteLLM Proxy callback that appends cache-usage records to JSONL."""

    def log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        write_litellm_proxy_success(kwargs, response_obj, start_time, end_time)

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        write_litellm_proxy_success(kwargs, response_obj, start_time, end_time)


def default_litellm_proxy_log_path() -> Path:
    configured = os.environ.get("CATOP_LITELLM_LOG")
    if configured:
        return Path(configured)
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "catop" / DEFAULT_PROXY_LOG_NAME
    root = os.environ.get("XDG_STATE_HOME")
    if root:
        return Path(root) / "catop" / DEFAULT_PROXY_LOG_NAME
    return Path.home() / ".local" / "state" / "catop" / DEFAULT_PROXY_LOG_NAME


def write_litellm_proxy_success(
    kwargs: dict[str, Any],
    response_obj: Any,
    start_time: datetime,
    end_time: datetime,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    record = normalize_litellm_proxy_success(kwargs, response_obj, start_time, end_time)
    output_path = path or default_litellm_proxy_log_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return record


def normalize_litellm_proxy_success(
    kwargs: dict[str, Any],
    response_obj: Any,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    response = _plain_data(response_obj)
    usage = _plain_data(_get(response, "usage"))
    litellm_params = _plain_data(kwargs.get("litellm_params")) or {}
    metadata = _plain_data(litellm_params.get("metadata")) or {}
    standard_metadata = _plain_data(kwargs.get("standard_logging_object")) or {}

    model = _coalesce(
        kwargs.get("model"),
        _get(response, "model"),
        standard_metadata.get("model"),
        "unknown",
    )
    provider = _coalesce(
        kwargs.get("custom_llm_provider"),
        litellm_params.get("custom_llm_provider"),
        metadata.get("litellm_provider"),
        standard_metadata.get("custom_llm_provider"),
        "unknown",
    )
    cost = _coalesce(
        kwargs.get("response_cost"),
        standard_metadata.get("cost"),
        standard_metadata.get("response_cost"),
    )

    return {
        "source": "litellm-proxy",
        "agent": _coalesce(metadata.get("agent"), "litellm-proxy"),
        "timestamp": _format_time(end_time),
        "startTime": _format_time(start_time),
        "endTime": _format_time(end_time),
        "id": _coalesce(_get(response, "id"), kwargs.get("litellm_call_id"), kwargs.get("call_id")),
        "session_id": _coalesce(
            metadata.get("session_id"),
            metadata.get("thread_id"),
            metadata.get("conversation_id"),
            metadata.get("trace_id"),
            kwargs.get("litellm_call_id"),
            kwargs.get("call_id"),
            _get(response, "id"),
            "-",
        ),
        "project": _coalesce(
            metadata.get("project"),
            metadata.get("team_id"),
            metadata.get("user_api_key_alias"),
            kwargs.get("user"),
            "-",
        ),
        "model": model,
        "provider": provider,
        "usage": usage or {},
        "response_cost": float(cost) if cost is not None else None,
        "metadata": metadata,
    }


def _plain_data(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_data(item) for item in value]
    for method in ("model_dump", "dict"):
        candidate = getattr(value, method, None)
        if callable(candidate):
            try:
                return _plain_data(candidate())
            except TypeError:
                continue
    try:
        items = vars(value).items()
    except TypeError:
        return str(value)
    return {key: _plain_data(item) for key, item in items if not key.startswith("_")}


def _get(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        return data.get(key)
    return getattr(data, key, None)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone().isoformat()


proxy_handler_instance = CatopLiteLLMProxyLogger()
