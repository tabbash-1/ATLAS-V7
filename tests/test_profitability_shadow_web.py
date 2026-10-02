from pathlib import Path

def test_web_shadow_is_explicitly_isolated():
 s=Path("cloud_web_only_final.py").read_text()
 assert '"/api/research/profitability-shadow"' in s
 assert 'payload["can_override_production"]=False' in s
 assert 'payload["production_threshold"]=68' in s

def test_ui_labels_shadow_not_production():
 s=Path("index.html").read_text()
 assert "PROFITABILITY RESEARCH SHADOW" in s
 assert "Isolated from Production Final Gate" in s
 assert "68 LOCKED" in s
 assert "/api/research/profitability-shadow" in s
