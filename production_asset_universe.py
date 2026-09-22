"""Canonical Production asset-universe guard for ATLAS.

This module is deliberately strategy-neutral. It does not score, qualify,
promote, demote, or execute trades. It constrains the interactive Production
decision surface to the frozen base universe plus the prospective expansion
cohort. Expansion assets use the exact same decision rules and are explicitly
labelled so their forward evidence can remain separate from the base cohort.
"""
from __future__ import annotations

VERSION = "ATLAS_PRODUCTION_ASSET_UNIVERSE_V3_HYPE_EXPANSION"
ASSET_UNIVERSE_EPOCH = "ASSET_EXPANSION_V1_2026-09-18"
ASSET_UNIVERSE_ACTIVATED_AT = "2026-09-18T20:00:00Z"
BASE_PRODUCTION_ASSETS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ZECUSDT",
)
EXPANSION_PRODUCTION_ASSETS = (
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "LTCUSDT",
    "HYPEUSDT",
)
CANONICAL_PRODUCTION_ASSETS = BASE_PRODUCTION_ASSETS + EXPANSION_PRODUCTION_ASSETS


def cohort_for(symbol: str) -> str:
    normalized = str(symbol or "").upper().replace("BINANCE:", "")
    if normalized in EXPANSION_PRODUCTION_ASSETS:
        return "ASSET_EXPANSION_V1"
    if normalized in BASE_PRODUCTION_ASSETS:
        return "BASE_V1"
    return "UNSUPPORTED"


def enforce(atlas):
    """Fail closed to the canonical frozen asset universe."""
    assets = tuple(CANONICAL_PRODUCTION_ASSETS)
    atlas.ON_DEMAND_SYMBOLS = assets
    atlas.SYMBOLS = assets

    safe_mode = getattr(atlas, "WEB_SAFE_MODE", None)
    if isinstance(safe_mode, dict):
        safe_mode["production_asset_universe"] = {
            "enabled": True,
            "version": VERSION,
            "assets": list(assets),
            "count": len(assets),
            "base_assets": list(BASE_PRODUCTION_ASSETS),
            "expansion_assets": list(EXPANSION_PRODUCTION_ASSETS),
            "asset_universe_epoch": ASSET_UNIVERSE_EPOCH,
            "activated_at": ASSET_UNIVERSE_ACTIVATED_AT,
            "expansion_rules": "IDENTICAL_TO_BASE_PRODUCTION_RULES",
            "research_symbols_can_override": False,
            "score_changed": False,
            "threshold_changed": False,
            "live_execution": False,
        }
    return {
        "enabled": True,
        "version": VERSION,
        "assets": list(assets),
        "count": len(assets),
        "base_assets": list(BASE_PRODUCTION_ASSETS),
        "expansion_assets": list(EXPANSION_PRODUCTION_ASSETS),
        "asset_universe_epoch": ASSET_UNIVERSE_EPOCH,
        "activated_at": ASSET_UNIVERSE_ACTIVATED_AT,
        "expansion_rules": "IDENTICAL_TO_BASE_PRODUCTION_RULES",
        "research_symbols_can_override": False,
        "score_changed": False,
        "threshold_changed": False,
        "live_execution": False,
    }
