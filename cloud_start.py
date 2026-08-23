#!/usr/bin/env python3
import os, runpy, shutil, urllib.parse
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
os.environ.setdefault("ATLAS_RESEARCH_COVERAGE_STALE_HOURS", "8")
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

# Production UI cache hardening.
release_token = (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("ATLAS_RELEASE") or "atlas-v7").strip()
release_token = "".join(c for c in release_token if c.isalnum() or c in "-_")[:40] or "atlas-v7"
index_path = BASE / "index.html"
if index_path.exists():
    html = index_path.read_text(encoding="utf-8")
    old_theme = '<script src="theme-toggle.js"></script>'
    versioned = (
        f'<script src="theme-toggle.js?v={release_token}"></script>\n'
        f'  <script src="atlas-product-shell.js?v={release_token}"></script>'
    )
    if old_theme in html:
        html = html.replace(old_theme, versioned, 1)
        index_path.write_text(html, encoding="utf-8")

# Force browsers to revalidate the UI after each production deploy.
import collector_server as _collector
_original_end_headers = _collector.Handler.end_headers

def _production_no_cache_headers(self):
    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    self.send_header("Pragma", "no-cache")
    self.send_header("Expires", "0")
    _original_end_headers(self)

_collector.Handler.end_headers = _production_no_cache_headers

# Serialize JSONL writes before any background worker or bridge wrapper starts.
from storage_hardening import install as _install_storage_hardening
_install_storage_hardening(_collector)

# Bridge newly stored cloud-forward observations into Pattern Memory with exact
# forward lineage. This remains research-only and fail-open to forward storage.
from research_memory_bridge import install as _install_research_memory_bridge
_install_research_memory_bridge(_collector)

# Production keeps the hardened runtime with a separate research sampling lane.
entrypoint = "atlas_research_runtime_server.py"
print(f"ATLAS production boot: data={DATA_DIR} runtime=resilient-free-research release={release_token}")
runpy.run_path(str(BASE / entrypoint), run_name="__main__")
