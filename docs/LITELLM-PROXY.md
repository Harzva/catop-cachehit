# LiteLLM Proxy Integration

`catop` ships a LiteLLM Proxy callback that writes successful request usage to
local JSONL. This is the first real proxy integration path because it uses
LiteLLM's public callback interface and does not depend on private database
schema details.

## 1. Install catop in the Proxy environment

```bash
python -m pip install "catop @ git+https://github.com/Harzva/catop-cachehit.git"
```

For local development:

```bash
python -m pip install -e .
```

## 2. Set the log path

```bash
export CATOP_LITELLM_LOG="$HOME/.local/state/catop/litellm-proxy-cachehit.jsonl"
```

On Windows PowerShell:

```powershell
$env:CATOP_LITELLM_LOG="$env:LOCALAPPDATA\catop\litellm-proxy-cachehit.jsonl"
```

If the variable is not set, `catop` uses a platform default under the local user
state/cache directory.

## 3. Add the callback to LiteLLM Proxy config

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

litellm_settings:
  callbacks: catop.litellm_proxy.proxy_handler_instance
```

Start the proxy:

```bash
litellm --config config.yaml --debug
```

## 4. Watch cachehit from another terminal

```bash
catop --litellm-proxy-log --window today
```

Point at a custom path:

```bash
catop --litellm-proxy-log ./litellm-proxy-cachehit.jsonl --group-by session
```

Open a single session after finding its ID:

```bash
catop --litellm-proxy-log --session agent-loop-42 --once
```

## Logged Shape

The callback writes one JSON object per successful request. It stores token
usage, model/provider, project, session, cost, and metadata. It intentionally
does not persist prompt or response text.

```json
{
  "source": "litellm-proxy",
  "agent": "litellm-proxy",
  "session_id": "agent-loop-42",
  "project": "agent-loop",
  "model": "gpt-4o",
  "provider": "openai",
  "usage": {
    "prompt_tokens": 1000,
    "completion_tokens": 120,
    "prompt_tokens_details": { "cached_tokens": 400 }
  },
  "response_cost": 0.002
}
```

## Why Callback First?

LiteLLM also has database/API logging paths, but the callback is the smallest
production slice:

- No direct dependency on Proxy database migrations.
- Works with the same JSONL parser already used by `catop --file`.
- Keeps privacy simple by logging usage metadata rather than prompt content.
- Can be replaced or complemented later by DB/API readers.
