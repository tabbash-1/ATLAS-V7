#!/usr/bin/env python3
"""ATLAS compatibility entrypoint.

Render historically used ``python3 cloud_start.py`` from a manually configured
service. Keep this path permanently safe: on Render it delegates to the minimal
web-only runtime plus the final fail-closed TRADE READY guard so dashboard
settings cannot accidentally boot the heavy research process or bypass final
4-12H direction authority. ``cloud_web_only.py`` remains the delegated base
runtime and is loaded by ``cloud_web_only_final.py`` before the last guard.

The pre-change full runtime is preserved in Git history and on branch
``backup/pre-render-safe-cloud-start-20260828``.
"""
from __future__ import annotations
import os
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ.setdefault("ATLAS_CLOUD_FORWARD_MIN_SCORE", "68")

if os.environ.get("RENDER"):
    os.environ["ATLAS_CLOUD_FORWARD_ENABLED"] = "0"
    os.environ["ATLAS_WEB_ONLY"] = "1"
    # Patch the final runtime before it is parsed/executed so the ranking endpoint
    # is downstream of FINAL_TRADE_GATE and cannot influence trade eligibility.
    from opportunity_readiness_boot_patch import apply as _apply_opportunity_readiness_patch
    _apply_opportunity_readiness_patch()
    # UI is diagnostic-only and refreshes only on explicit user action.
    from opportunity_ranking_ui_boot_patch import apply as _apply_opportunity_ranking_ui_patch
    _apply_opportunity_ranking_ui_patch()
    # Show the exact closed-candle evidence still required while WAIT. This layer
    # is read-only and cannot alter score, threshold, geometry, or Final Gate.
    from actionable_wait_evidence_boot_patch import apply as _apply_actionable_wait_evidence_patch
    _apply_actionable_wait_evidence_patch()

    # Install the staged-decision research endpoint at the same safe initialization
    # point used by cloud_web_only_final.py: Render/closed-candle patches run before
    # collector_server is imported. The overlay intercepts one read-only endpoint
    # and never wraps or replaces production_decision.
    from render_boot_patch import apply as _apply_render_boot_patch
    from closed_candle_htf_boot_patch import apply as _apply_closed_candle_htf_boot_patch
    _apply_render_boot_patch()
    _apply_closed_candle_htf_boot_patch()
    import collector_server as _atlas_web_runtime
    from staged_shadow_api_overlay import install as _install_staged_shadow_api
    STAGED_SHADOW_API = _install_staged_shadow_api(_atlas_web_runtime)

    # Keep the final guard as the last authority in the deployed request path.
    print("ATLAS cloud_start compatibility guard: RENDER -> cloud_web_only_final.py", flush=True)
    print(f"Staged shadow API: {STAGED_SHADOW_API['version']} (research only)", flush=True)
    runpy.run_path(str(BASE / "cloud_web_only_final.py"), run_name="__main__")
else:
    # Local/manual invocations use the memory-safe web stack by default too.
    # Heavy research continues in scheduled GitHub workflows rather than sharing
    # memory with the interactive server.
    print("ATLAS cloud_start compatibility guard: local -> cloud_start_web.py", flush=True)
    runpy.run_path(str(BASE / "cloud_start_web.py"), run_name="__main__")
