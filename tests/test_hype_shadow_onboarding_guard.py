"""Regression tests for canonical Production asset-universe isolation."""
from production_asset_universe import CANONICAL_PRODUCTION_ASSETS, enforce


def test_canonical_production_universe_remains_seven_assets():
    assert CANONICAL_PRODUCTION_ASSETS == (
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
        "BNBUSDT", "DOGEUSDT", "ZECUSDT",
    )
    assert "HYPEUSDT" not in CANONICAL_PRODUCTION_ASSETS


def test_hype_cannot_leak_into_production_runtime():
    class Atlas:
        ON_DEMAND_SYMBOLS = ("HYPEUSDT",)
        SYMBOLS = ("HYPEUSDT",)
        WEB_SAFE_MODE = {}

    atlas = Atlas()
    result = enforce(atlas)
    assert tuple(atlas.SYMBOLS) == CANONICAL_PRODUCTION_ASSETS
    assert tuple(atlas.ON_DEMAND_SYMBOLS) == CANONICAL_PRODUCTION_ASSETS
    assert result["research_symbols_can_override"] is False
    assert result["count"] == 7
