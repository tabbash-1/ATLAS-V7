#!/usr/bin/env python3
"""Render entrypoint that installs the final ATLAS trade-ready guard last."""
from __future__ import annotations
import os
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent
ns = runpy.run_path(str(BASE / "cloud_web_only.py"), run_name="atlas_cloud_web_only_base")
atlas = ns["atlas"]
from final_trade_ready_guard import install as install_final_trade_ready_guard
FINAL_TRADE_READY_GUARD = install_final_trade_ready_guard(atlas)
if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):
    atlas.WEB_SAFE_MODE["final_trade_ready_guard"] = FINAL_TRADE_READY_GUARD

if __name__ == "__main__":
    os.chdir(atlas.ROOT)
    port = int(os.environ.get("PORT", "8080"))
    print("ATLAS Render WEB-ONLY safe mode + FINAL TRADE READY guard", flush=True)
    print(f"Final trade-ready guard: {FINAL_TRADE_READY_GUARD['version']}", flush=True)
    print(f"Listening on {port}", flush=True)
    ns["Server"](("0.0.0.0", port), ns["WebOnlyHandler"]).serve_forever(poll_interval=0.5)
