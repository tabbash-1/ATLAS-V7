#!/usr/bin/env python3
"""Render entrypoint that installs the final ATLAS trade-ready guard last."""
from __future__ import annotations
import os
import runpy
import urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
ns = runpy.run_path(str(BASE / "cloud_web_only.py"), run_name="atlas_cloud_web_only_base")
atlas = ns["atlas"]
from final_trade_ready_guard import install as install_final_trade_ready_guard
FINAL_TRADE_READY_GUARD = install_final_trade_ready_guard(atlas)
if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):
    atlas.WEB_SAFE_MODE["final_trade_ready_guard"] = FINAL_TRADE_READY_GUARD

from whale_intelligence import VERSION as WHALE_INTELLIGENCE_VERSION
from whale_intelligence import filter_feed as filter_whale_feed
from whale_intelligence import load_snapshot as load_whale_snapshot


def _whale_snapshot():
    # Read on request so a newly committed verified snapshot can become visible
    # after deploy without any web-process collector or hidden mutable state.
    return load_whale_snapshot(BASE)


class FinalWebOnlyHandler(ns["WebOnlyHandler"]):
    """Web-only handler with explicit final-decision and whale-data contracts."""
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/runtime/status":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "service": "ATLAS_V7",
                "runtime": "WEB_ONLY_FINAL",
                "web_safe_mode": atlas.WEB_SAFE_MODE,
                "final_trade_ready_guard": FINAL_TRADE_READY_GUARD,
                "production_threshold": float(atlas.CLOUD_FORWARD_MIN_SCORE),
                "product_horizon": "4-12H",
                "whale_intelligence": {
                    "version": WHALE_INTELLIGENCE_VERSION,
                    "state": whale.get("state"),
                    "data_available": whale.get("data_available"),
                    "provider": whale.get("provider"),
                    "last_updated": whale.get("last_updated"),
                },
                "research_only": True,
                "analysis_only": True,
                "live_execution": False,
            })
        if parsed.path == "/api/whales/status":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "version": whale.get("version"),
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "provider": whale.get("provider"),
                "provider_authenticated": whale.get("provider_authenticated"),
                "last_updated": whale.get("last_updated"),
                "snapshot_age_minutes": whale.get("snapshot_age_minutes"),
                "stale_after_minutes": whale.get("stale_after_minutes"),
                "rejected_rows": whale.get("rejected_rows"),
                "rejection_reasons": whale.get("rejection_reasons"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/top10":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "count": len(whale.get("top10") or []),
                "top10": whale.get("top10") or [],
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/feed":
            q = urllib.parse.parse_qs(parsed.query)
            whale = _whale_snapshot()
            rows = filter_whale_feed(
                whale,
                asset=(q.get("asset") or [None])[0],
                flow_type=(q.get("flow_type") or [None])[0],
                bias=(q.get("bias") or [None])[0],
            )
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "count": len(rows),
                "feed": rows,
                "filters": {
                    "asset": (q.get("asset") or [None])[0],
                    "flow_type": (q.get("flow_type") or [None])[0],
                    "bias": (q.get("bias") or [None])[0],
                },
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/consensus":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "consensus": whale.get("consensus"),
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        return super().do_GET()


if __name__ == "__main__":
    os.chdir(atlas.ROOT)
    port = int(os.environ.get("PORT", "8080"))
    print("ATLAS Render WEB-ONLY safe mode + FINAL TRADE READY guard", flush=True)
    print(f"Final trade-ready guard: {FINAL_TRADE_READY_GUARD['version']}", flush=True)
    print(f"Whale intelligence: {WHALE_INTELLIGENCE_VERSION}", flush=True)
    print(f"Listening on {port}", flush=True)
    ns["Server"](("0.0.0.0", port), FinalWebOnlyHandler).serve_forever(poll_interval=0.5)
