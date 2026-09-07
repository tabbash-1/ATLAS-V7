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


class FinalWebOnlyHandler(ns["WebOnlyHandler"]):
    """Web-only handler with an explicit runtime contract for Production smoke tests."""
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/runtime/status":
            return self._json({
                "ok": True,
                "service": "ATLAS_V7",
                "runtime": "WEB_ONLY_FINAL",
                "web_safe_mode": atlas.WEB_SAFE_MODE,
                "final_trade_ready_guard": FINAL_TRADE_READY_GUARD,
                "production_threshold": float(atlas.CLOUD_FORWARD_MIN_SCORE),
                "product_horizon": "4-12H",
                "research_only": True,
                "analysis_only": True,
                "live_execution": False,
            })
        return super().do_GET()


if __name__ == "__main__":
    os.chdir(atlas.ROOT)
    port = int(os.environ.get("PORT", "8080"))
    print("ATLAS Render WEB-ONLY safe mode + FINAL TRADE READY guard", flush=True)
    print(f"Final trade-ready guard: {FINAL_TRADE_READY_GUARD['version']}", flush=True)
    print(f"Listening on {port}", flush=True)
    ns["Server"](("0.0.0.0", port), FinalWebOnlyHandler).serve_forever(poll_interval=0.5)
