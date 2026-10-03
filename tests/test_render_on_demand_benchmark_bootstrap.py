from pathlib import Path

def test_render_bootstrap_is_fail_safe_and_research_only():
    t=(Path(__file__).resolve().parents[1]/"render_boot_patch.py").read_text()
    assert "ensure_on_demand_benchmark_snapshot()" in t
    assert '"--days", "180"' in t
    assert 'timeout=75' in t
    assert 'data.get("research_only") is True' in t
    assert 'data.get("production_effect") == "NONE"' in t
    assert 'data.get("can_override_production") is False' in t
    assert "Production unaffected" in t
