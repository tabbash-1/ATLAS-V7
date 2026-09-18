"""ATLAS research-only asset universe.

This universe may expand evidence collection without changing the canonical
Production asset contract. Symbols here cannot override FINAL_TRADE_GATE.
"""
from production_asset_universe import CANONICAL_PRODUCTION_ASSETS

VERSION = "ATLAS_RESEARCH_ASSET_UNIVERSE_V1"
RESEARCH_ONLY_ASSETS = ("HYPEUSDT",)
RESEARCH_ASSETS = tuple(dict.fromkeys(CANONICAL_PRODUCTION_ASSETS + RESEARCH_ONLY_ASSETS))


def symbols():
    return RESEARCH_ASSETS


def safety_contract():
    return {
        "version": VERSION,
        "assets": list(RESEARCH_ASSETS),
        "research_only_assets": list(RESEARCH_ONLY_ASSETS),
        "production_assets": list(CANONICAL_PRODUCTION_ASSETS),
        "research_only": True,
        "can_override_production": False,
        "changes_production_universe": False,
        "changes_score": False,
        "changes_threshold": False,
        "changes_geometry": False,
        "live_execution": False,
    }
