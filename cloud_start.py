#!/usr/bin/env python3
import os, runpy, shutil, urllib.parse, re
from pathlib import Path

BASE = Path(__file__).resolve().parent
if os.environ.get("RENDER") and not os.environ.get("ATLAS_DATA_DIR"):
    persistent_mount = Path("/var/data")
    if persistent_mount.exists() and os.access(str(persistent_mount), os.W_OK): os.environ["ATLAS_DATA_DIR"] = str(persistent_mount)
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
DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", str(BASE / "data"))); DATA_DIR.mkdir(parents=True, exist_ok=True)
for name in ("smart_money_archive.jsonl","smart_money_archive.json","confluence_memory.jsonl","event_memory.jsonl","champion_challenger_forward.jsonl","trade_geometry.jsonl","canary_stage_state.json","confirmed_opportunity_alerts.jsonl","ai_trade_council.jsonl"):
    source,target=BASE/name,DATA_DIR/name
    if source.exists() and not target.exists(): shutil.copy2(source,target)
release_token=(os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("ATLAS_RELEASE") or "atlas-v7").strip(); release_token="".join(c for c in release_token if c.isalnum() or c in "-_")[:40] or "atlas-v7"
index_path=BASE/"index.html"
if index_path.exists():
    html=index_path.read_text(encoding="utf-8")
    old_theme='<script src="theme-toggle.js"></script>'
    versioned=f'<script src="theme-toggle.js?v={release_token}"></script>\n  <script src="atlas-product-shell.js?v={release_token}"></script>'
    if old_theme in html: html=html.replace(old_theme,versioned,1)

    if 'id="atlasAiCouncilCard"' not in html:
        panel='''\n      <section id="atlasAiCouncilCard" class="card metrics-card ai-council-card">\n        <div class="card-head"><div><strong>ATLAS AI TRADE COUNCIL</strong><div class="muted small">Production + Tactical 1–3H + Bull/Bear + Counterfactual + Hybrid Judge</div></div><span id="aiCouncilBadge" class="pill neutral">WAITING</span></div>\n        <div class="ai-council-grid">\n          <div class="ai-kpi"><span>Production</span><b id="aiProdDecision">—</b><small id="aiProdScore">—</small></div>\n          <div class="ai-kpi"><span>Tactical 1–3H</span><b id="aiTactical">—</b><small id="aiTacticalRR">—</small></div>\n          <div class="ai-kpi"><span>AI Judge</span><b id="aiJudge">—</b><small id="aiConfidence">—</small></div>\n          <div class="ai-kpi"><span>Hybrid</span><b id="aiHybrid">—</b><small id="aiHybridSub">—</small></div>\n        </div>\n        <div class="ai-council-split">\n          <div class="ai-case"><div class="panel-title">BULL CASE</div><div id="aiBullCase" class="muted small">Waiting for analysis.</div></div>\n          <div class="ai-case"><div class="panel-title">BEAR CASE</div><div id="aiBearCase" class="muted small">Waiting for analysis.</div></div>\n        </div>\n        <div class="ai-counterfactual"><div class="panel-title">BEST ACTION / COUNTERFACTUAL</div><div id="aiBestAction" class="ai-best-action">—</div><div id="aiGeometry" class="muted small">—</div><div id="aiTrigger" class="muted tiny">—</div></div>\n        <div id="aiEvidence" class="comparison-box muted small">Evidence will appear after Analyze Live.</div>\n      </section>\n'''
        anchor='<section class="grid lower-grid">'
        if anchor in html: html=html.replace(anchor,panel+'\n      '+anchor,1)
        else: html=html.replace('</main>',panel+'\n    </main>',1)

    decision_script=f'<script src="atlas-production-decision.js?v={release_token}"></script>'
    calibration_script=f'<script src="outcome-calibration-ui.js?v={release_token}"></script>'
    html=re.sub(r'<script[^>]+src=["\']atlas-production-decision\.js(?:\?[^"\']*)?["\'][^>]*></script>','',html)
    html=re.sub(r'<script[^>]+src=["\']outcome-calibration-ui\.js(?:\?[^"\']*)?["\'][^>]*></script>','',html)
    html=html.replace('</body>',f'  {decision_script}\n  {calibration_script}\n</body>',1) if '</body>' in html else html+'\n'+decision_script+'\n'+calibration_script+'\n'
    index_path.write_text(html,encoding="utf-8")
app_path=BASE/"app.js"
if app_path.exists():
    app_js=app_path.read_text(encoding="utf-8"); hype_asset="  { name: 'Hyperliquid / USDT', symbol: 'BINANCE:HYPEUSDT', cls: 'Crypto' },\n"; anchor="  { name: 'Zcash / USDT', symbol: 'BINANCE:ZECUSDT', cls: 'Crypto' },\n"
    if "BINANCE:HYPEUSDT" not in app_js and anchor in app_js: app_path.write_text(app_js.replace(anchor,anchor+hype_asset,1),encoding="utf-8")
import collector_server as _collector
if 'HYPEUSDT' not in _collector.ON_DEMAND_SYMBOLS: _collector.ON_DEMAND_SYMBOLS=tuple(_collector.ON_DEMAND_SYMBOLS)+('HYPEUSDT',)
from hype_market_data import install as _install_hype_market_data; _install_hype_market_data(_collector)
_collector.SYMBOLS=tuple(_collector.ON_DEMAND_SYMBOLS)
_original_end_headers=_collector.Handler.end_headers
def _production_no_cache_headers(self):
    self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0"); self.send_header("Pragma","no-cache"); self.send_header("Expires","0"); _original_end_headers(self)
_collector.Handler.end_headers=_production_no_cache_headers
from storage_hardening import install as _install_storage_hardening; _install_storage_hardening(_collector)
from production_signal_scoring import install as _install_production_signal_scoring; _install_production_signal_scoring(_collector)
from production_continuation_scoring import install as _install_production_continuation_scoring; _install_production_continuation_scoring(_collector)
from production_decision_api import install as _install_production_decision_api; _install_production_decision_api(_collector)
from decision_engine_v7 import install as _install_decision_engine_v7; _install_decision_engine_v7(_collector)
from execution_risk_management import install as _install_execution_risk_management; _install_execution_risk_management(_collector)
from ai_trade_council import install as _install_ai_trade_council; _install_ai_trade_council(_collector)
from research_memory_bridge import install as _install_research_memory_bridge; _install_research_memory_bridge(_collector)
from trade_path_settlement import install_geometry_freezer as _install_trade_geometry_freezer; _install_trade_geometry_freezer(_collector)
from trade_outcome_runtime import install as _install_trade_outcome_runtime; _install_trade_outcome_runtime(_collector)
from outcome_calibration_runtime import install as _install_outcome_calibration_runtime; _install_outcome_calibration_runtime(_collector)
from production_reliability import install as _install_production_reliability; _install_production_reliability(_collector)
entrypoint="atlas_research_runtime_server.py"
print(f"ATLAS production boot: data={DATA_DIR} runtime=resilient-free-research release={release_token}")
runpy.run_path(str(BASE/entrypoint),run_name="__main__")