from pathlib import Path
from types import SimpleNamespace

from canonical_asset_ui_boot_patch import transform_app_js
from production_asset_universe import (
    CANONICAL_PRODUCTION_ASSETS,
    VERSION,
    enforce,
)

EXPECTED = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ZECUSDT",
)


def test_enforce_replaces_research_symbol_leak_with_exact_canonical_universe():
    atlas = SimpleNamespace(
        ON_DEMAND_SYMBOLS=EXPECTED + ("HYPEUSDT",),
        SYMBOLS=("BTCUSDT", "HYPEUSDT"),
        WEB_SAFE_MODE={},
    )

    state = enforce(atlas)

    assert CANONICAL_PRODUCTION_ASSETS == EXPECTED
    assert atlas.ON_DEMAND_SYMBOLS == EXPECTED
    assert atlas.SYMBOLS == EXPECTED
    assert "HYPEUSDT" not in atlas.ON_DEMAND_SYMBOLS
    assert state["version"] == VERSION
    assert state["count"] == 7
    assert state["score_changed"] is False
    assert state["threshold_changed"] is False
    assert state["research_symbols_can_override"] is False
    assert atlas.WEB_SAFE_MODE["production_asset_universe"] == state


def test_production_ui_removes_hype_and_filters_saved_assets():
    root = Path(__file__).resolve().parents[1]
    original = (root / "app.js").read_text(encoding="utf-8")
    patched = transform_app_js(original)

    assert "BINANCE:HYPEUSDT" not in patched
    assert "const CANONICAL_PRODUCTION_SYMBOLS = new Set(" in patched
    assert "CANONICAL_PRODUCTION_SYMBOLS.has(String(a.symbol || '').toUpperCase())" in patched
    for symbol in EXPECTED:
        assert f"BINANCE:{symbol}" in patched


def test_render_entrypoint_routes_through_canonical_universe_launcher():
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloud_start.py").read_text(encoding="utf-8")
    launcher = (root / "cloud_production_canonical.py").read_text(encoding="utf-8")

    assert 'cloud_production_canonical.py' in source
    assert 'enforce_production_asset_universe(atlas)' in launcher
    assert 'apply_canonical_asset_ui_patch(BASE)' in launcher
    assert 'cloud_web_only_final.py' in launcher
