from __future__ import annotations

from collections.abc import Sequence

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from catop.models import CacheEvent
from catop.pricing import PriceCatalog
from catop.stats import aggregate_events, summarize_events


def make_dashboard(
    events: Sequence[CacheEvent],
    catalog: PriceCatalog,
    *,
    group_by: tuple[str, ...],
    top: int,
    source_label: str,
    window_label: str = "all",
) -> Group:
    summary = summarize_events(events, catalog)
    rows = aggregate_events(events, catalog, group_by=group_by)[:top]

    title = Text("catop", style="bold cyan")
    title.append(" cachehit monitor", style="bold")
    summary_text = Text()
    summary_text.append(
        (
            f"req={summary.request_count} in={_tokens(summary.input_tokens)} "
            f"read={_tokens(summary.cached_tokens)} write={_tokens(summary.cache_creation_tokens)} "
            f"miss={_tokens(summary.miss_tokens)} "
        ),
        style="bold",
    )
    summary_text.append(f"hit={summary.hit_rate * 100:5.1f}% ", style="cyan")
    summary_text.append(f"saved={_money(summary.saved_usd)}", style="green")

    source_text = Text(
        (
            f"out={_tokens(summary.output_tokens)} reason={_tokens(summary.reasoning_tokens)} "
            f"est_cost={_money(summary.estimated_cost_usd)} "
            f"source={source_label} window={window_label} price={catalog.source}"
        ),
        style="dim",
    )
    if summary.actual_cost_usd:
        source_text.append(f" | observed_cost={_money(summary.actual_cost_usd)}")
    source_text.append(" | Ctrl+C quit | --help options")

    table = Table(expand=True, show_lines=False, box=box.ASCII)
    table.add_column("Group", overflow="crop", no_wrap=True, ratio=2)
    table.add_column("Req", justify="right", no_wrap=True)
    table.add_column("In", justify="right", no_wrap=True)
    table.add_column("Read", justify="right", no_wrap=True)
    table.add_column("Write", justify="right", no_wrap=True)
    table.add_column("Miss", justify="right", no_wrap=True)
    table.add_column("Hit%", justify="right", no_wrap=True)
    table.add_column("Saved", justify="right", no_wrap=True)

    for row in rows:
        hit_style = "green" if row.hit_rate >= 0.7 else "yellow" if row.hit_rate >= 0.4 else "red"
        table.add_row(
            _group_label(row.agent, row.provider, row.model, row.project, row.session_id),
            str(row.request_count),
            _tokens(row.input_tokens),
            _tokens(row.cached_tokens),
            _tokens(row.cache_creation_tokens),
            _tokens(row.miss_tokens),
            Text(f"{row.hit_rate * 100:5.1f}%", style=hit_style),
            _money(row.saved_usd),
        )

    if not rows:
        table.add_row("-", "0", "0", "0", "0", "0", "0.0%", "$0.0000")

    footer = Text(
        "Cache fields: read=cache hit, write=cache creation, miss=uncached input.",
        style="dim",
    )
    return Group(Panel(Group(summary_text, source_text), title=title, box=box.ASCII), table, footer)


def make_session_detail(
    events: Sequence[CacheEvent],
    catalog: PriceCatalog,
    *,
    source_label: str,
    session_id: str,
) -> Group:
    summary = summarize_events(events, catalog)
    title = Text("catop", style="bold cyan")
    title.append(f" session {session_id}", style="bold")

    summary_text = Text(
        (
            f"req={summary.request_count} in={_tokens(summary.input_tokens)} "
            f"read={_tokens(summary.cached_tokens)} write={_tokens(summary.cache_creation_tokens)} "
            f"miss={_tokens(summary.miss_tokens)} hit={summary.hit_rate * 100:5.1f}% "
            f"saved={_money(summary.saved_usd)}"
        ),
        style="bold",
    )
    source_text = Text(f"source={source_label} price={catalog.source}", style="dim")

    table = Table(expand=True, show_lines=False, box=box.ASCII)
    table.add_column("Time", no_wrap=True)
    table.add_column("In", justify="right", no_wrap=True)
    table.add_column("Read", justify="right", no_wrap=True)
    table.add_column("Wr", justify="right", no_wrap=True)
    table.add_column("Miss", justify="right", no_wrap=True)
    table.add_column("Out", justify="right", no_wrap=True)
    table.add_column("Rsn", justify="right", no_wrap=True)
    table.add_column("Hit", justify="right", no_wrap=True)
    table.add_column("Saved", justify="right", no_wrap=True)

    for event in sorted(events, key=lambda item: item.timestamp):
        saved = catalog.estimate_saved_usd(
            event.model,
            event.input_tokens,
            event.cached_tokens,
            cache_creation_tokens=event.cache_creation_tokens,
            output_tokens=event.output_tokens,
            reasoning_tokens=event.reasoning_tokens,
            provider=event.provider,
        )
        hit_style = (
            "green" if event.hit_rate >= 0.7 else "yellow" if event.hit_rate >= 0.4 else "red"
        )
        table.add_row(
            event.timestamp.astimezone().strftime("%H:%M:%S"),
            _tokens(event.input_tokens),
            _tokens(event.cached_tokens),
            _tokens(event.cache_creation_tokens),
            _tokens(event.miss_tokens),
            _tokens(event.output_tokens),
            _tokens(event.reasoning_tokens),
            Text(f"{event.hit_rate * 100:5.1f}%", style=hit_style),
            _money(saved),
        )

    if not events:
        table.add_row("-", "0", "0", "0", "0", "0", "0", "0.0%", "$0.0000")

    footer = Text(
        "Session detail: Wr=cache write, Rsn=reasoning tokens; rows are timestamp ordered.",
        style="dim",
    )
    return Group(Panel(Group(summary_text, source_text), title=title, box=box.ASCII), table, footer)


def _tokens(value: int) -> str:
    return f"{value:,}"


def _money(value: float) -> str:
    return f"${value:,.4f}"


def _group_label(agent: str, provider: str, model: str, project: str, session_id: str) -> str:
    parts = [part for part in (agent, provider, model, project) if part != "*"]
    if session_id != "*":
        parts.append(session_id)
    return " / ".join(parts) if parts else "*"
