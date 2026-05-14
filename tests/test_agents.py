from __future__ import annotations

from pathlib import Path

from catop.agents import scan_agent_events


def test_scan_claude_code_jsonl(tmp_path: Path) -> None:
    session = tmp_path / "projects" / "repo-a" / "session.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        (
            '{"type":"assistant","message":{"model":"claude-sonnet-4-5",'
            '"usage":{"input_tokens":100,"output_tokens":10,'
            '"cache_read_input_tokens":70,"cache_creation_input_tokens":5}},'
            '"timestamp":"2026-05-14T00:00:00Z"}\n'
        ),
        encoding="utf-8",
    )

    events = scan_agent_events("claude-code", root=tmp_path)

    assert len(events) == 1
    assert events[0].agent == "claude-code"
    assert events[0].project == "repo-a"
    assert events[0].input_tokens == 175


def test_scan_codex_jsonl(tmp_path: Path) -> None:
    session = tmp_path / "sessions" / "repo-a" / "session.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        (
            '{"type":"session_configured","payload":{"model":"gpt-5.1-codex-max",'
            '"model_provider":"openai","cwd":"/tmp/repo-a"}}\n'
            '{"type":"event_msg","payload":{"type":"token_count","info":{'
            '"last_token_usage":{"input_tokens":100,"output_tokens":10,'
            '"cached_input_tokens":25,"reasoning_output_tokens":5}}}}\n'
        ),
        encoding="utf-8",
    )

    events = scan_agent_events("codex", root=tmp_path)

    assert len(events) == 1
    assert events[0].agent == "codex"
    assert events[0].project == "repo-a"
    assert events[0].model == "gpt-5.1-codex-max"
    assert events[0].cached_tokens == 25
    assert events[0].reasoning_tokens == 5
