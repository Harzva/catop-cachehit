<div align="center">
  <h1>catop</h1>
  <p><strong>A top-like terminal monitor for LLM cache hits, cached tokens, and dollars saved.</strong></p>
  <p><strong>只做一件事：</strong>监视和统计 LLM prompt cache hit。</p>
  <p>
    <a href="#quick-start">Quick Start</a>
    ·
    <a href="#litellm-jsonl-input">LiteLLM Input</a>
    ·
    <a href="#roadmap">Roadmap</a>
    ·
    <a href="https://github.com/Harzva/catop-cachehit/actions">Actions</a>
  </p>
  <p>
    <a href="https://github.com/Harzva/catop-cachehit/actions/workflows/ci.yml">
      <img src="https://github.com/Harzva/catop-cachehit/actions/workflows/ci.yml/badge.svg" alt="CI" />
    </a>
    <img src="https://img.shields.io/badge/python-3.9%2B-2563EB" alt="Python 3.9+" />
    <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-10A37F" alt="Platforms" />
    <img src="https://img.shields.io/badge/license-MIT-111827" alt="MIT License" />
  </p>
</div>

<p align="center">
  <img src="docs/assets/catop-demo.svg" alt="catop terminal preview" width="860" />
</p>

## What It Watches

`catop` is intentionally narrow. It does not try to become a full observability
platform. It watches the prompt-cache economics that matter when agents, RAG
systems, coding loops, and eval runners make repeated LLM calls.

| Signal | Meaning |
| --- | --- |
| Cache hit rate | How much of your input token traffic was served from prompt cache |
| Cached tokens | Input tokens that used provider-side prompt caching |
| Miss tokens | Input tokens billed as normal non-cached input |
| Saved USD | Estimated savings from cached input token pricing |
| Grouping | Provider, model, and project/team attribution |

## Quick Start

Run the demo stream:

```bash
python -m pip install -e .
catop --demo
```

Render one snapshot and exit:

```bash
catop --demo --once --top 5
```

Use it after publishing to GitHub:

```bash
python -m pip install "catop @ git+https://github.com/Harzva/catop-cachehit.git"
catop --demo --once
```

## LiteLLM JSONL Input

`catop` already accepts OpenAI/LiteLLM-style JSONL records. Each line is one
request log object.

```bash
catop --file examples/litellm-cachehit.jsonl --once
```

Pipe logs from another process:

```bash
tail -f ./litellm-requests.jsonl | catop --stdin --once
```

Example record:

```json
{
  "model": "gpt-4o",
  "litellm_provider": "openai",
  "metadata": { "project": "agent-loop" },
  "usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 120,
    "prompt_tokens_details": { "cached_tokens": 400 }
  },
  "response_cost": 0.002
}
```

`catop` also recognizes common cache fields such as `cache_read_input_tokens`,
`cached_tokens`, `cache_hit_tokens`, and `cache_creation_input_tokens`.

## Savings Formula

On startup, `catop` loads LiteLLM's public model price map and caches it locally
for 24 hours. If the network is unavailable, it falls back to a small embedded
price table for common demo models.

```text
saved_usd = cached_tokens * (input_cost_per_token - cache_read_input_token_cost)
```

If a log record includes actual response cost, `catop` displays it separately as
observed cost. Estimated savings and observed cost are not mixed.

## Command Reference

```bash
catop --help
```

| Option | Purpose |
| --- | --- |
| `--demo` | Run with simulated cache-hit traffic |
| `--file PATH` | Read LiteLLM/OpenAI-style JSONL request logs |
| `--stdin` | Read JSONL request logs from standard input |
| `--once` | Print one snapshot and exit |
| `--top N` | Limit grouped rows in the dashboard |
| `--group-by provider,model,project` | Choose grouping dimensions |
| `--refresh-prices` | Refresh the LiteLLM price cache |

## Architecture

```mermaid
flowchart LR
    A["LiteLLM / OpenAI JSONL logs"] --> B["catop ingest"]
    C["Demo stream"] --> B
    D["LiteLLM price map"] --> E["local TTL cache"]
    E --> F["savings estimator"]
    B --> G["cache-hit aggregator"]
    F --> G
    G --> H["Rich terminal dashboard"]
```

## Repository Layout

```text
src/catop/
  cli.py       command entry point
  demo.py      simulated cache-hit stream
  ingest.py    LiteLLM/OpenAI-style JSONL parser
  pricing.py   LiteLLM price-map cache and fallback prices
  render.py    Rich terminal dashboard
  stats.py     cache-hit aggregation and savings calculation
tests/         focused unit tests
examples/      small JSONL fixtures for quick local checks
```

## Roadmap

| Stage | Status | Scope |
| --- | --- | --- |
| Repository cleanup | Done | `src/catop`, package metadata, tests, CI, README |
| Real MVP | Started | LiteLLM price map cache and JSONL log ingestion |
| LiteLLM integrations | Next | Proxy DB/API reader and custom callback example |
| Cross-platform binaries | Started | GitHub Actions artifacts for Linux, Windows, macOS |
| Native installers | Later | `.deb`, `.rpm`, `.exe`, Homebrew or signed macOS artifact |

## Development

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest tests
```

Build package artifacts locally:

```bash
python -m pip install build
python -m build
```

The packaging workflow can build one-file binaries with PyInstaller on Linux,
Windows, and macOS.

## Scope

`catop` is not a general APM, tracing backend, billing dashboard, or LLM proxy.
Its job is to make cache-hit behavior visible enough that you can improve cache
reuse and see the estimated savings quickly.

## License

MIT
