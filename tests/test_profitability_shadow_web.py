from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def test_shadow_snapshot_is_non_production():
 d=json.loads((ROOT/'status/profitability-shadow-web-latest.json').read_text())
 assert d['safety']['research_only'] is True
 assert d['safety']['can_override_production'] is False
 assert d['safety']['production_source_of_truth']=='FINAL_TRADE_GATE'
 assert d['safety']['production_threshold']==68
 assert d['safety']['automatic_promotion'] is False

def test_web_contract_exposes_shadow_separately():
 py=(ROOT/'cloud_web_only_final.py').read_text(); html=(ROOT/'index.html').read_text(); js=(ROOT/'profitability-shadow-ui.js').read_text()
 assert '/api/research/profitability-shadow' in py
 assert 'profitability-shadow-ui.js' in html
 assert 'PROFITABILITY RESEARCH SHADOW' in html
 assert 'FINAL_TRADE_GATE' in js
 assert 'production_decision(' not in js
