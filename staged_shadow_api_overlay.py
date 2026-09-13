"""Read-only HTTP overlay for staged ATLAS shadow diagnostics.

Installed only in the web runtime. It intercepts one research endpoint and never
wraps, replaces, or mutates atlas.production_decision.
"""
from __future__ import annotations

import urllib.parse

from atlas_decision_architecture import CORE_ASSETS
from staged_decision_shadow import VERSION, build_shadow

API_PATH = "/api/research/staged-decision-shadow"


def install(atlas):
    handler = atlas.Handler
    if getattr(handler, "_atlas_staged_shadow_api_installed", False):
        return {
            "enabled": True, "version": VERSION, "path": API_PATH,
            "shadow_only": True, "can_override_production": False,
        }

    original_do_get = handler.do_GET

    def shadow_do_get(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != API_PATH:
            return original_do_get(self)
        q = urllib.parse.parse_qs(parsed.query)
        symbol = str((q.get("symbol") or ["BTCUSDT"])[0]).upper().replace("BINANCE:", "")
        if symbol not in CORE_ASSETS:
            return self._json({
                "ok": False,
                "error": "unsupported canonical symbol",
                "symbol": symbol,
                "supported_symbols": list(CORE_ASSETS),
                "shadow_only": True,
                "research_only": True,
                "can_override_production": False,
                "live_execution": False,
            }, 400)
        before_callable = atlas.production_decision
        row = before_callable(symbol)
        result = build_shadow(row, symbol=symbol)
        result["production_decision_callable_unchanged"] = atlas.production_decision is before_callable
        return self._json(result, 200 if result.get("ok") else 400)

    handler.do_GET = shadow_do_get
    handler._atlas_staged_shadow_api_installed = True
    return {
        "enabled": True,
        "version": VERSION,
        "path": API_PATH,
        "canonical_assets": list(CORE_ASSETS),
        "shadow_only": True,
        "research_only": True,
        "can_override_production": False,
        "live_execution": False,
    }
