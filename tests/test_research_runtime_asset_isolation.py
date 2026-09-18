from pathlib import Path


def test_research_runtime_uses_isolated_research_universe():
    text = Path("atlas_research_runtime_server.py").read_text(encoding="utf-8")
    assert "import research_asset_universe" in text
    assert "for symbol in research_asset_universe.symbols():" in text
    assert "atlas.read_forward(), research_asset_universe.symbols()," in text


def test_research_runtime_does_not_expand_production_symbols():
    text = Path("atlas_research_runtime_server.py").read_text(encoding="utf-8")
    assert "atlas.SYMBOLS =" not in text
    assert "atlas.ON_DEMAND_SYMBOLS =" not in text
