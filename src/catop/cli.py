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
from catop.demo import generate_demo_event, generate_demo_events
from catop.ingest import read_jsonl_events, read_stdin_events
from catop.models import CacheEvent
from catop.pricing import load_litellm_price_catalog
from catop.render import make_dashboard
from catop.stats import VALID_GROUP_FIELDS, parse_group_by


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
    use_demo = args.demo or (args.file is None and not args.stdin)
    source_label = _source_label(args, use_demo)

    if args.once:
        events = _load_events(args, use_demo=use_demo, limit=args.limit)
        console.print(
            make_dashboard(
                events,
                catalog,
                group_by=group_by,
                top=args.top,
                source_label=source_label,
            )
        )
        return 0

    events = deque(_load_events(args, use_demo=use_demo, limit=args.limit), maxlen=args.limit)
    rng = random.Random()
    with Live(
        make_dashboard(
            list(events),
            catalog,
            group_by=group_by,
            top=args.top,
            source_label=source_label,
        ),
        console=console,
        screen=True,
        refresh_per_second=4,
    ) as live:
        while True:
            if use_demo:
                events.append(generate_demo_event(rng))
            elif args.file is not None:
                events = deque(read_jsonl_events(args.file)[-args.limit :], maxlen=args.limit)
            live.update(
                make_dashboard(
                    list(events),
                    catalog,
                    group_by=group_by,
                    top=args.top,
                    source_label=source_label,
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
        "--interval",
        type=float,
        default=1.0,
        help="Live refresh interval in seconds.",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Maximum events kept in memory.")
    parser.add_argument("--top", type=int, default=25, help="Maximum grouped rows to show.")
    parser.add_argument(
        "--group-by",
        default="provider,model,project",
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


def _load_events(args: argparse.Namespace, *, use_demo: bool, limit: int) -> list[CacheEvent]:
    if args.stdin:
        return read_stdin_events()[-limit:]
    if args.file is not None:
        return read_jsonl_events(args.file)[-limit:]
    if use_demo:
        return generate_demo_events(15)[-limit:]
    return []


def _source_label(args: argparse.Namespace, use_demo: bool) -> str:
    if args.stdin:
        return "stdin-jsonl"
    if args.file is not None:
        return str(args.file)
    if use_demo:
        return "demo"
    return "empty"
