from pathlib import Path

def test_on_demand_evidence_ui_is_research_only():
    js=(Path(__file__).resolve().parents[1]/"atlas-on-demand-evidence-ui.js").read_text()
    assert "/api/research/on-demand-analysis-benchmark" in js
    assert "cannot override FINAL_TRADE_GATE" in js

def test_render_boot_includes_on_demand_evidence_ui():
    text=(Path(__file__).resolve().parents[1]/"render_boot_patch.py").read_text()
    assert "atlas-on-demand-evidence-ui.js" in text
