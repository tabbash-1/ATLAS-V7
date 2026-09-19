#!/usr/bin/env python3
"""Final Render launcher with the canonical Production asset boundary.

Loads the existing final web stack without starting its server, constrains the
interactive Production universe and browser asset list, then starts the same
final handler. Research files may still contain other symbols; they cannot
become Production symbols.
"""
from __future__ import annotations

import os
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent

final_ns = runpy.run_path(
    str(BASE / "cloud_web_only_final.py"),
    run_name="atlas_cloud_web_only_final_base",
)
atlas = final_ns["atlas"]

from production_asset_universe import enforce as enforce_production_asset_universe
from canonical_asset_ui_boot_patch import apply as apply_canonical_asset_ui_patch

PRODUCTION_ASSET_UNIVERSE = enforce_production_asset_universe(atlas)
PRODUCTION_ASSET_UI = apply_canonical_asset_ui_patch(BASE)
if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):
    atlas.WEB_SAFE_MODE["production_asset_ui"] = PRODUCTION_ASSET_UI

if __name__ == "__main__":
    os.chdir(atlas.ROOT)
    port = int(os.environ.get("PORT", "8080"))
    print("ATLAS Render canonical Production universe guard", flush=True)
    print(
        "Production assets: " + ",".join(PRODUCTION_ASSET_UNIVERSE["assets"]),
        flush=True,
    )
    print(
        f"Production UI assets: {PRODUCTION_ASSET_UI['count']} "
        f"HYPE exposed={PRODUCTION_ASSET_UI['hype_exposed']}",
        flush=True,
    )
    final_ns["ns"]["Server"](
        ("0.0.0.0", port), final_ns["FinalWebOnlyHandler"]
    ).serve_forever(poll_interval=0.5)
