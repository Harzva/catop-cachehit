from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LITELLM_PRICE_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
DEFAULT_PRICE_CACHE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class ModelPrice:
    model: str
    provider: str
    input_cost_per_token: float | None
    cache_read_input_token_cost: float | None
    cache_creation_input_token_cost: float | None = None
    output_cost_per_token: float | None = None

    def estimate_saved_usd(self, cached_tokens: int) -> float:
        if (
            cached_tokens <= 0
            or self.input_cost_per_token is None
            or self.cache_read_input_token_cost is None
        ):
            return 0.0
        delta = max(self.input_cost_per_token - self.cache_read_input_token_cost, 0.0)
        return cached_tokens * delta


FALLBACK_PRICE_DATA: dict[str, dict[str, Any]] = {
    "gpt-4o": {
        "litellm_provider": "openai",
        "input_cost_per_token": 2.5e-6,
        "output_cost_per_token": 1.0e-5,
        "cache_read_input_token_cost": 1.25e-6,
    },
    "gpt-4o-mini": {
        "litellm_provider": "openai",
        "input_cost_per_token": 1.5e-7,
        "output_cost_per_token": 6.0e-7,
        "cache_read_input_token_cost": 7.5e-8,
    },
    "claude-sonnet": {
        "litellm_provider": "anthropic",
        "input_cost_per_token": 3.0e-6,
        "output_cost_per_token": 1.5e-5,
        "cache_creation_input_token_cost": 3.75e-6,
        "cache_read_input_token_cost": 3.0e-7,
    },
    "claude-sonnet-4-5": {
        "litellm_provider": "anthropic",
        "input_cost_per_token": 3.0e-6,
        "output_cost_per_token": 1.5e-5,
        "cache_creation_input_token_cost": 3.75e-6,
        "cache_read_input_token_cost": 3.0e-7,
    },
    "deepseek-chat": {
        "litellm_provider": "deepseek",
        "input_cost_per_token": 2.8e-7,
        "output_cost_per_token": 4.2e-7,
        "cache_read_input_token_cost": 2.8e-8,
    },
    "deepseek/deepseek-chat": {
        "litellm_provider": "deepseek",
        "input_cost_per_token": 2.8e-7,
        "output_cost_per_token": 4.2e-7,
        "cache_creation_input_token_cost": 0.0,
        "cache_read_input_token_cost": 2.8e-8,
    },
    "deepseek-reasoner": {
        "litellm_provider": "deepseek",
        "input_cost_per_token": 2.8e-7,
        "output_cost_per_token": 4.2e-7,
        "cache_read_input_token_cost": 2.8e-8,
    },
    "deepseek/deepseek-reasoner": {
        "litellm_provider": "deepseek",
        "input_cost_per_token": 2.8e-7,
        "output_cost_per_token": 4.2e-7,
        "cache_read_input_token_cost": 2.8e-8,
    },
}


class PriceCatalog:
    def __init__(self, prices: dict[str, ModelPrice], source: str) -> None:
        self._prices = prices
        self.source = source

    @classmethod
    def from_raw(cls, raw: dict[str, Any], source: str) -> PriceCatalog:
        prices: dict[str, ModelPrice] = {}
        for model, data in raw.items():
            if not isinstance(data, dict):
                continue
            price = ModelPrice(
                model=model,
                provider=str(data.get("litellm_provider") or data.get("provider") or "unknown"),
                input_cost_per_token=_optional_float(data.get("input_cost_per_token")),
                output_cost_per_token=_optional_float(data.get("output_cost_per_token")),
                cache_read_input_token_cost=_optional_float(data.get("cache_read_input_token_cost")),
                cache_creation_input_token_cost=_optional_float(
                    data.get("cache_creation_input_token_cost")
                ),
            )
            has_input_price = price.input_cost_per_token is not None
            has_cache_price = price.cache_read_input_token_cost is not None
            if has_input_price or has_cache_price:
                prices[model.lower()] = price
        return cls(prices, source=source)

    @classmethod
    def fallback(cls) -> PriceCatalog:
        return cls.from_raw(FALLBACK_PRICE_DATA, source="fallback")

    def get(self, model: str, provider: str | None = None) -> ModelPrice | None:
        for alias in _model_aliases(model, provider):
            price = self._prices.get(alias.lower())
            if price is not None:
                return price
        return None

    def estimate_saved_usd(
        self,
        model: str,
        cached_tokens: int,
        provider: str | None = None,
    ) -> float:
        price = self.get(model, provider=provider)
        if price is None:
            return 0.0
        return price.estimate_saved_usd(cached_tokens)

    def provider_for(self, model: str, provider: str | None = None) -> str:
        price = self.get(model, provider=provider)
        if price is None:
            return provider or "unknown"
        return price.provider

    def __len__(self) -> int:
        return len(self._prices)


def default_cache_dir() -> Path:
    configured = os.environ.get("CATOP_CACHE_DIR")
    if configured:
        return Path(configured)
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "catop"
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "catop"
    return Path.home() / ".cache" / "catop"


def load_litellm_price_catalog(
    *,
    refresh: bool = False,
    ttl_seconds: int = DEFAULT_PRICE_CACHE_SECONDS,
    cache_dir: Path | None = None,
    timeout_seconds: float = 10.0,
) -> PriceCatalog:
    cache_dir = cache_dir or default_cache_dir()
    cache_file = cache_dir / "model_prices_and_context_window.json"

    if not refresh and _is_fresh(cache_file, ttl_seconds):
        return _load_cached(cache_file, source="cache")

    try:
        raw = _fetch_json(LITELLM_PRICE_URL, timeout_seconds)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
        return PriceCatalog.from_raw(raw, source="litellm")
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        if cache_file.exists():
            return _load_cached(cache_file, source="stale-cache")
        return PriceCatalog.fallback()


def _load_cached(cache_file: Path, source: str) -> PriceCatalog:
    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    return PriceCatalog.from_raw(raw, source=source)


def _fetch_json(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "catop/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_fresh(path: Path, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0 or not path.exists():
        return False
    return time.time() - path.stat().st_mtime < ttl_seconds


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model_aliases(model: str, provider: str | None = None) -> list[str]:
    clean_model = (model or "").strip()
    clean_provider = (provider or "").strip()
    aliases = [clean_model]
    if clean_provider and clean_model:
        aliases.append(f"{clean_provider}/{clean_model}")
    if "/" in clean_model:
        aliases.append(clean_model.split("/", 1)[1])
    return [alias for alias in aliases if alias]
