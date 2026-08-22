#!/usr/bin/env python3
import os, runpy, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", str(BASE / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# collector_server reads persistent state directly from ATLAS_DATA_DIR.
# On first cloud boot, seed any legacy repository-root archives/state into the
# persistent directory only when the persistent target does not already exist.
# This preserves existing cloud data across deploys and avoids copying state
# back into the ephemeral application directory.
persistent_candidates = [
    "smart_money_archive.jsonl",
    "smart_money_archive.json",
    "confluence_memory.jsonl",
    "event_memory.jsonl",
    "champion_challenger_forward.jsonl",
    "canary_stage_state.json",
    "confirmed_opportunity_alerts.jsonl",
]
for name in persistent_candidates:
    source = BASE / name
    target = DATA_DIR / name
    if source.exists() and not target.exists():
        shutil.copy2(source, target)

# atlas_ai_server subclasses the existing collector handler and preserves all
# legacy ATLAS routes/loops while adding /api/ai/analyze. The collector itself
# remains untouched so rollback is one-file simple.
runpy.run_path(str(BASE / "atlas_ai_server.py"), run_name="__main__")
