from __future__ import annotations

import argparse
import random
import time
from collections import deque
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.live import Live

from catop import __version__
from catop.agents import SUPPORTED_AGENTS, scan_many_agents
from catop.demo import generate_demo_event, generate_demo_events
from catop.ingest import read_jsonl_events, read_stdin_events
from catop.litellm_proxy import default_litellm_proxy_log_path
from catop.models import CacheEvent
from catop.pricing import load_litellm_price_catalog
from catop.render import make_dashboard, make_session_detail
from catop.stats import VALID_GROUP_FIELDS, parse_group_by
from catop.time_windows import WINDOW_CHOICES, filter_events_by_window


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        group_by = parse_group_by(args.group_by)
    except ValueError as exc:
        parser.error(str(exc))

    catalog = load_litellm_price_catalog(
        refresh=args.refresh_prices,
        ttl_seconds=args.price_cache_ttl,
        timeout_seconds=args.price_timeout,
    )
    console = Console()
    agents = _selected_agents(args)
    use_demo = args.demo or (
        args.file is None and not args.stdin and not agents and args.litellm_proxy_log is None
    )
    source_label = _source_label(args, use_demo, agents)

    if args.once:
        events = _apply_filters(
            _load_events(args, use_demo=use_demo, limit=args.limit, agents=agents),
            window=args.window,
            session_id=args.session,
        )
        if args.session:
            console.print(
                make_session_detail(
                    events,
                    catalog,
                    source_label=source_label,
                    session_id=args.session,
                )
            )
            return 0
        console.print(
            make_dashboard(
                events,
                catalog,
                group_by=group_by,
                top=args.top,
                source_label=source_label,
                window_label=args.window,
            )
        )
        return 0

    events = deque(
        _apply_filters(
            _load_events(args, use_demo=use_demo, limit=args.limit, agents=agents),
            window=args.window,
            session_id=args.session,
        ),
        maxlen=args.limit,
    )
    rng = random.Random()
    with Live(
        _make_view(
            list(events),
            catalog=catalog,
            group_by=group_by,
            top=args.top,
            source_label=source_label,
            window_label=args.window,
            session_id=args.session,
        ),
        console=console,
        screen=True,
        refresh_per_second=4,
    ) as live:
        while True:
            if use_demo:
                events.append(generate_demo_event(rng))
            elif args.file is not None:
                events = deque(
                    _apply_filters(
                        _recent_events(read_jsonl_events(args.file), args.limit),
                        window=args.window,
                        session_id=args.session,
                    ),
                    maxlen=args.limit,
                )
            elif args.litellm_proxy_log is not None:
                events = deque(
                    _apply_filters(
                        _recent_events(
                            _read_optional_jsonl_events(args.litellm_proxy_log),
                            args.limit,
                        ),
                        window=args.window,
                        session_id=args.session,
                    ),
                    maxlen=args.limit,
                )
            elif agents:
                events = deque(
                    _apply_filters(
                        _recent_events(scan_many_agents(agents), args.limit),
                        window=args.window,
                        session_id=args.session,
                    ),
                    maxlen=args.limit,
                )
            current_events = _apply_filters(
                list(events),
                window=args.window,
                session_id=args.session,
            )
            live.update(
                _make_view(
                    current_events,
                    catalog=catalog,
                    group_by=group_by,
                    top=args.top,
                    source_label=source_label,
                    window_label=args.window,
                    session_id=args.session,
                )
            )
            time.sleep(args.interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catop",
        description="Top-like LLM cache-hit monitor with LiteLLM pricing support.",
    )
    parser.add_argument("--version", action="version", version=f"catop {__version__}")
    parser.add_argument("--demo", action="store_true", help="Run with simulated cache-hit traffic.")
    parser.add_argument("--once", action="store_true", help="Render one snapshot and exit.")
    parser.add_argument("--file", type=Path, help="Read LiteLLM/OpenAI-style JSONL request logs.")
    parser.add_argument("--stdin", action="store_true", help="Read JSONL request logs from stdin.")
    parser.add_argument(
        "--litellm-proxy-log",
        nargs="?",
        const=default_litellm_proxy_log_path(),
        type=Path,
        help="Read catop's LiteLLM Proxy callback JSONL log. Defaults to CATOP_LITELLM_LOG.",
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=SUPPORTED_AGENTS,
        help="Scan a local coding-agent session store. Repeat for multiple agents.",
    )
    parser.add_argument(
        "--scan-agents",
        action="store_true",
        help="Scan every built-in local agent source currently supported by catop.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Live refresh interval in seconds.",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Maximum events kept in memory.")
    parser.add_argument("--top", type=int, default=25, help="Maximum grouped rows to show.")
    parser.add_argument(
        "--window",
        choices=WINDOW_CHOICES,
        default="all",
        help="Time window using local time: all, today, week, or month.",
    )
    parser.add_argument("--session", help="Show a single session detail view.")
    parser.add_argument(
        "--group-by",
        default="agent,provider,model,project",
        help=f"Comma-separated grouping fields: {', '.join(VALID_GROUP_FIELDS)}.",
    )
    parser.add_argument(
        "--refresh-prices",
        action="store_true",
        help="Refresh the LiteLLM model price map before rendering.",
    )
    parser.add_argument(
        "--price-cache-ttl",
        type=int,
        default=24 * 60 * 60,
        help="Seconds before the cached LiteLLM price map is considered stale.",
    )
    parser.add_argument(
        "--price-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait when fetching the LiteLLM price map.",
    )
    return parser


def _load_events(
    args: argparse.Namespace,
    *,
    use_demo: bool,
    limit: int,
    agents: tuple[str, ...],
) -> list[CacheEvent]:
    if args.stdin:
        return _recent_events(read_stdin_events(), limit)
    if args.file is not None:
        return _recent_events(read_jsonl_events(args.file), limit)
    if args.litellm_proxy_log is not None:
        return _recent_events(_read_optional_jsonl_events(args.litellm_proxy_log), limit)
    if agents:
        return _recent_events(scan_many_agents(agents), limit)
    if use_demo:
        return _recent_events(generate_demo_events(15), limit)
    return []


def _recent_events(events: list[CacheEvent], limit: int) -> list[CacheEvent]:
    return sorted(events, key=lambda event: event.timestamp)[-limit:]


def _apply_filters(
    events: list[CacheEvent],
    *,
    window: str,
    session_id: str | None,
) -> list[CacheEvent]:
    filtered = filter_events_by_window(events, window)
    if session_id:
        filtered = [event for event in filtered if event.session_id == session_id]
    return filtered


def _make_view(
    events: list[CacheEvent],
    *,
    catalog,
    group_by: tuple[str, ...],
    top: int,
    source_label: str,
    window_label: str,
    session_id: str | None,
):
    if session_id:
        return make_session_detail(
            events,
            catalog,
            source_label=source_label,
            session_id=session_id,
        )
    return make_dashboard(
        events,
        catalog,
        group_by=group_by,
        top=top,
        source_label=source_label,
        window_label=window_label,
    )


def _read_optional_jsonl_events(path: Path) -> list[CacheEvent]:
    if not path.exists():
        return []
    return read_jsonl_events(path)


def _source_label(args: argparse.Namespace, use_demo: bool, agents: tuple[str, ...]) -> str:
    if args.stdin:
        return "stdin-jsonl"
    if args.file is not None:
        return str(args.file)
    if args.litellm_proxy_log is not None:
        return f"litellm-proxy:{args.litellm_proxy_log}"
    if agents:
        return "agents:" + ",".join(agents)
    if use_demo:
        return "demo"
    return "empty"


def _selected_agents(args: argparse.Namespace) -> tuple[str, ...]:
    agents = list(args.agent or [])
    if args.scan_agents:
        agents.extend(SUPPORTED_AGENTS)
    return tuple(dict.fromkeys(agents))
