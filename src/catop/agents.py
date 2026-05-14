from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from catop.ingest import event_from_litellm_record, events_from_jsonl
from catop.models import CacheEvent

SUPPORTED_AGENTS = ("claude-code", "codex")


def scan_agent_events(agent: str, *, root: Path | None = None) -> list[CacheEvent]:
    if agent == "claude-code":
        return _scan_claude_code(root)
    if agent == "codex":
        return _scan_codex(root)
    raise ValueError(f"Unsupported agent: {agent}")


def scan_many_agents(agents: Iterable[str]) -> list[CacheEvent]:
    events: list[CacheEvent] = []
    for agent in agents:
        events.extend(scan_agent_events(agent))
    return sorted(events, key=lambda event: event.timestamp)


def _scan_claude_code(root: Path | None = None) -> list[CacheEvent]:
    base = root or Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
    paths = list((base / "projects").glob("**/*.jsonl"))
    paths.extend((base / "transcripts").glob("**/*.jsonl"))
    events: list[CacheEvent] = []
    for path in _dedupe_paths(paths):
        project = _project_from_claude_path(base, path)
        events.extend(
            _read_path_events(
                path,
                default_agent="claude-code",
                default_project=project,
                claude_usage_semantics=True,
            )
        )
    return events


def _scan_codex(root: Path | None = None) -> list[CacheEvent]:
    base = root or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    paths = list((base / "sessions").glob("**/*.jsonl"))
    events: list[CacheEvent] = []
    for path in _dedupe_paths(paths):
        events.extend(_read_codex_path_events(path, default_project=_project_from_path(path)))
    return events


def _read_path_events(
    path: Path,
    *,
    default_agent: str,
    default_project: str,
    claude_usage_semantics: bool = False,
) -> list[CacheEvent]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return list(
                events_from_jsonl(
                    handle,
                    default_agent=default_agent,
                    default_project=default_project,
                    claude_usage_semantics=claude_usage_semantics,
                )
            )
    except OSError:
        return []


def _read_codex_path_events(path: Path, *, default_project: str) -> list[CacheEvent]:
    events: list[CacheEvent] = []
    current_model: str | None = None
    current_provider: str | None = None
    current_project = default_project
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                payload = record.get("payload")
                if isinstance(payload, dict):
                    if payload.get("model"):
                        current_model = str(payload["model"])
                    if payload.get("model_provider"):
                        current_provider = str(payload["model_provider"])
                    if payload.get("cwd"):
                        current_project = Path(str(payload["cwd"])).name or current_project
                    info = payload.get("info")
                    if isinstance(info, dict) and isinstance(info.get("last_token_usage"), dict):
                        if current_model and not record.get("model"):
                            record["model"] = current_model
                        if current_provider and not record.get("provider"):
                            record["provider"] = current_provider
                        event = event_from_litellm_record(
                            record,
                            default_agent="codex",
                            default_project=current_project,
                        )
                        if event.has_usage:
                            events.append(event)
    except OSError:
        return []
    return events


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(path)
    return result


def _project_from_claude_path(base: Path, path: Path) -> str:
    projects_root = (base / "projects").resolve()
    try:
        relative = path.resolve().relative_to(projects_root)
    except ValueError:
        return "transcripts"
    if relative.parts:
        return relative.parts[0]
    return _project_from_path(path)


def _project_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent or "-"
