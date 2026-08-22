#!/usr/bin/env python3
import os, runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", str(BASE / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# The existing collector uses its project directory for the archive.
# On a cloud host, keep a persistent copy and restore it before launch.
archive_candidates = [
    "smart_money_archive.jsonl",
    "smart_money_archive.json",
]
for name in archive_candidates:
    persistent = DATA_DIR / name
    local = BASE / name
    if persistent.exists() and not local.exists():
        local.write_bytes(persistent.read_bytes())

# atlas_ai_server subclasses the existing collector handler and preserves all
# legacy ATLAS routes/loops while adding /api/ai/analyze. The collector itself
# remains untouched so rollback is one-file simple.
runpy.run_path(str(BASE / "atlas_ai_server.py"), run_name="__main__")
