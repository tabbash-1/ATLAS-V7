#!/usr/bin/env python3
import os, runpy, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Production-safe defaults. Existing explicit environment values always win.
if os.environ.get("RENDER") and not os.environ.get("ATLAS_DATA_DIR"):
    persistent_mount = Path("/var/data")
    if persistent_mount.exists() and os.access(str(persistent_mount), os.W_OK):
        os.environ["ATLAS_DATA_DIR"] = str(persistent_mount)

os.environ.setdefault("ATLAS_RELEASE", "V7-ALPHA25-CLOUD-RC1")
os.environ.setdefault("ATLAS_CLOUD_FORWARD_ENABLED", "1")
os.environ.setdefault("ATLAS_CLOUD_FORWARD_INTERVAL_SECONDS", "3600")
os.environ.setdefault("ATLAS_CLOUD_FORWARD_MIN_SCORE", "68")
os.environ.setdefault("ATLAS_CLOUD_FORWARD_MAX_PER_CYCLE", "3")
os.environ.setdefault("ATLAS_RESEARCH_SAMPLE_MIN_SCORE", "50")
os.environ.setdefault("ATLAS_RESEARCH_SAMPLE_MAX_PER_CYCLE", "3")
os.environ.setdefault("ATLAS_ALERT_MIN_SCORE", "82")
os.environ.setdefault("ATLAS_ALERT_MIN_RR", "2.0")
os.environ.setdefault("ATLAS_ALERT_MIN_VOLUME_QUALITY", "58")
os.environ.setdefault("ATLAS_ALERT_COOLDOWN_MINUTES", "240")

DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", str(BASE / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

# Production keeps the hardened free runtime, now with a separate research
# sampling lane. Signal/alert thresholds remain unchanged.
entrypoint = "atlas_research_runtime_server.py"
print(f"ATLAS production boot: data={DATA_DIR} runtime=resilient-free-research")
runpy.run_path(str(BASE / entrypoint), run_name="__main__")
