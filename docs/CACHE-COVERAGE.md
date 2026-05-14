# Cache Coverage

`catop` focuses on cache-hit monitoring rather than general LLM observability.
This document is the product contract for what is displayed today and what is
still planned.

## Displayed Today

| Field | Meaning |
| --- | --- |
| `req` | Number of parsed request/message usage records |
| `in` | Total input tokens after normalization |
| `read` | Cache-read tokens: input served from cache, the main cache-hit signal |
| `write` | Cache-creation/write tokens: input that creates or refreshes cache entries |
| `miss` | Input tokens not served by cache and not counted as cache creation |
| `out` | Output/completion tokens |
| `reason` | Reasoning/thinking tokens when the source exposes them |
| `hit%` | `read / input` |
| `est_cost` | Estimated cost after cache pricing |
| `observed_cost` | Actual logged cost when present in the source record |
| `saved` | Estimated savings against a no-cache baseline |

## Cache Fields Recognized

`catop` recognizes several naming conventions because providers and agents do
not agree on token field names.

| Normalized field | Accepted examples |
| --- | --- |
| Cache read | `cached_tokens`, `cache_read_input_tokens`, `cacheRead`, `cacheReads`, `input_cache_read`, `prompt_cache_hit_tokens`, `gen_ai.usage.cache_read.input_tokens` |
| Cache write/create | `cache_creation_input_tokens`, `cacheWrite`, `cacheWrites`, `cacheCreate`, `input_cache_creation`, `gen_ai.usage.cache_creation.input_tokens` |
| Input | `prompt_tokens`, `input_tokens`, `input`, `tokensIn`, `gen_ai.usage.input_tokens` |
| Output | `completion_tokens`, `output_tokens`, `output`, `tokensOut`, `gen_ai.usage.output_tokens` |
| Reasoning | `reasoning_tokens`, `reasoning_output_tokens`, `thoughtsTokenCount`, `gen_ai.usage.reasoning.output_tokens` |

## Provider Support

Provider support is pricing-driven. If a source emits provider/model and
token metadata, `catop` can display cache stats. Dollar estimates require
pricing.

| Provider family | Status |
| --- | --- |
| OpenAI / Codex | Supported through LiteLLM pricing; fallback for common demo models |
| Anthropic / Claude | Supported through LiteLLM pricing; cache creation pricing is used when available |
| DeepSeek | Supported through LiteLLM pricing; fallback for common demo models |
| Google / Gemini | Parsed when JSONL contains usage metadata; pricing depends on LiteLLM |
| Any LiteLLM model key | Parsed generically; pricing depends on LiteLLM cache fields |

## Agent Support

| Agent | Status | Default source |
| --- | --- | --- |
| Claude Code | Initial local scanner | `~/.claude/projects/**/*.jsonl`, `~/.claude/transcripts/**/*.jsonl` |
| Codex CLI | Initial local scanner | `$CODEX_HOME/sessions/**/*.jsonl` or `~/.codex/sessions/**/*.jsonl` |
| Generic LiteLLM/OpenAI logs | Supported | `--file` or `--stdin` JSONL |

Planned agents include OpenCode, Gemini CLI, Cursor, Copilot CLI, and other
sources that expose real cache token metadata.

## Reference-Informed Direction

The local research copies under `.research/` were used only to study product
shape, not to copy UI or code. The takeaways applied to `catop` are:

- Keep the first screen dense and operational: totals, hit rate, savings, and
  the top waste/savings groups.
- Treat cache read and cache write as separate signals because they answer
  different optimization questions.
- Make source support explicit so users know whether a number came from
  LiteLLM JSONL, Claude Code, Codex, or another scanner.
- Prefer a compact terminal surface first; richer views can come after the
  core cache economics are trustworthy.

## Still Needed

- Time-window filters such as today, week, month, and custom date ranges.
- A session-detail view so one row can expand into individual requests.
- More agent scanners with tests and documented storage locations.
- Provider fallback pricing beyond LiteLLM, such as OpenRouter/models.dev.
- Explicit freshness indicators for price cache age and source.
