"""Canonical Production asset-universe guard for ATLAS.

This module is deliberately strategy-neutral. It does not score, qualify,
promote, demote, or execute trades. It only constrains the interactive
Production decision surface to the seven assets in the product contract.
Research/shadow pipelines may study other symbols separately.
"""
from __future__ import annotations

VERSION = "ATLAS_PRODUCTION_ASSET_UNIVERSE_V1"
CANONICAL_PRODUCTION_ASSETS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ZECUSDT",
)


def enforce(atlas):
    """Fail closed to the canonical seven assets on the Production web runtime."""
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
        "research_symbols_can_override": False,
        "score_changed": False,
        "threshold_changed": False,
        "live_execution": False,
    }
