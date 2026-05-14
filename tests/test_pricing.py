from __future__ import annotations

from catop.pricing import PriceCatalog


def test_price_catalog_estimates_saved_from_cache_read_delta() -> None:
    catalog = PriceCatalog.from_raw(
        {
            "example-model": {
                "litellm_provider": "example",
                "input_cost_per_token": 2.0e-6,
                "cache_read_input_token_cost": 5.0e-7,
            }
        },
        source="test",
    )

    assert catalog.estimate_saved_usd("example-model", 1000, 1000) == 0.0015


def test_price_catalog_uses_provider_prefixed_alias() -> None:
    catalog = PriceCatalog.fallback()

    saved = catalog.estimate_saved_usd("deepseek-chat", 1000, 1000, provider="deepseek")

    assert saved > 0
