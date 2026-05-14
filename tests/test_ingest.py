from __future__ import annotations

import json

from catop.ingest import event_from_litellm_record, events_from_jsonl


def test_event_from_openai_style_usage_details() -> None:
    event = event_from_litellm_record(
        {
            "model": "gpt-4o",
            "litellm_provider": "openai",
            "metadata": {"project": "agent-loop"},
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 400},
                "completion_tokens_details": {"reasoning_tokens": 30},
            },
            "response_cost": 0.002,
            "timestamp": "2026-05-14T00:00:00Z",
        }
    )

    assert event.model == "gpt-4o"
    assert event.agent == "jsonl"
    assert event.provider == "openai"
    assert event.project == "agent-loop"
    assert event.input_tokens == 1000
    assert event.cached_tokens == 400
    assert event.reasoning_tokens == 30
    assert event.miss_tokens == 600
    assert event.actual_cost_usd == 0.002


def test_claude_code_semantics_add_cache_fields_to_total_input() -> None:
    event = event_from_litellm_record(
        {
            "type": "assistant",
            "message": {
                "model": "claude-sonnet-4-5",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 300,
                    "cache_creation_input_tokens": 50,
                },
            },
        },
        default_agent="claude-code",
        default_project="repo-a",
        claude_usage_semantics=True,
    )

    assert event.agent == "claude-code"
    assert event.project == "repo-a"
    assert event.input_tokens == 450
    assert event.cached_tokens == 300
    assert event.cache_creation_tokens == 50
    assert event.miss_tokens == 100


def test_events_from_jsonl_skips_invalid_lines() -> None:
    powershell_mojibake_prefix = chr(38168) + chr(32310)
    lines = [
        "not-json\n",
        "\ufeff" + json.dumps(
            {
                "model": "deepseek-chat",
                "usage": {"input_tokens": 500, "cache_read_input_tokens": 250},
            }
        ),
        (
            powershell_mojibake_prefix
            + '"model":"gpt-4o","usage":{"prompt_tokens":100,'
            + '"prompt_tokens_details":{"cached_tokens":50}}}'
        ),
    ]

    events = list(events_from_jsonl(lines))

    assert len(events) == 2
    assert events[0].cached_tokens == 250
    assert events[1].cached_tokens == 50


def test_events_from_jsonl_skips_records_without_usage() -> None:
    events = list(
        events_from_jsonl(['{"type":"session_configured","payload":{"model":"gpt-5.5"}}\n'])
    )

    assert events == []
