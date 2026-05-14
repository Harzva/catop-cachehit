from __future__ import annotations

from datetime import datetime, timezone

from catop.ingest import event_from_litellm_record
from catop.litellm_proxy import normalize_litellm_proxy_success, write_litellm_proxy_success


def test_normalize_litellm_proxy_success() -> None:
    record = normalize_litellm_proxy_success(
        {
            "model": "gpt-4o",
            "custom_llm_provider": "openai",
            "response_cost": 0.002,
            "litellm_call_id": "call-1",
            "litellm_params": {
                "metadata": {"project": "agent-loop", "session_id": "session-1", "agent": "codex"}
            },
        },
        {
            "id": "chatcmpl-1",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 600},
            },
        },
        datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 14, 1, 1, tzinfo=timezone.utc),
    )

    event = event_from_litellm_record(record)

    assert record["source"] == "litellm-proxy"
    assert event.agent == "codex"
    assert event.project == "agent-loop"
    assert event.session_id == "session-1"
    assert event.cached_tokens == 600
    assert event.actual_cost_usd == 0.002


def test_write_litellm_proxy_success_appends_jsonl(tmp_path) -> None:
    log_path = tmp_path / "litellm.jsonl"

    write_litellm_proxy_success(
        {"model": "deepseek-chat"},
        {"usage": {"input_tokens": 100, "cache_read_input_tokens": 20}},
        datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 14, 1, 1, tzinfo=timezone.utc),
        path=log_path,
    )

    assert log_path.read_text(encoding="utf-8").count("\n") == 1
