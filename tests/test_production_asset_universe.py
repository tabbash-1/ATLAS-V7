from pathlib import Path
from types import SimpleNamespace

from canonical_asset_ui_boot_patch import apply as apply_canonical_asset_ui_patch
from canonical_asset_ui_boot_patch import transform_app_js
from production_asset_universe import (
    ASSET_UNIVERSE_EPOCH,
    BASE_PRODUCTION_ASSETS,
    CANONICAL_PRODUCTION_ASSETS,
    EXPANSION_PRODUCTION_ASSETS,
    VERSION,
    cohort_for,
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
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "LTCUSDT",
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
    assert state["count"] == 11
    assert state["base_assets"] == list(BASE_PRODUCTION_ASSETS)
    assert state["expansion_assets"] == list(EXPANSION_PRODUCTION_ASSETS)
    assert state["asset_universe_epoch"] == ASSET_UNIVERSE_EPOCH
    assert state["expansion_rules"] == "IDENTICAL_TO_BASE_PRODUCTION_RULES"
    assert cohort_for("ADAUSDT") == "ASSET_EXPANSION_V1"
    assert cohort_for("BTCUSDT") == "BASE_V1"
    assert state["score_changed"] is False
    assert state["threshold_changed"] is False
    assert state["research_symbols_can_override"] is False
    assert atlas.WEB_SAFE_MODE["production_asset_universe"] == state


def test_production_ui_removes_hype_and_filters_saved_assets():
    root = Path(__file__).resolve().parents[1]
    original = (root / "app.js").read_text(encoding="utf-8")
    patched = transform_app_js(original)

    assert "HYPEUSDT" not in patched.upper()
    assert "const CANONICAL_PRODUCTION_SYMBOLS = new Set(" in patched
    assert "CANONICAL_PRODUCTION_SYMBOLS.has(String(a.symbol || '').toUpperCase())" in patched
    for symbol in EXPECTED:
        assert f"BINANCE:{symbol}" in patched


def test_production_ui_removes_hype_after_provider_rewrite():
    # Mirrors the real Render boot ordering where the legacy chart patch can
    # rewrite HYPE's provider before the canonical Production UI guard runs.
    rewritten = """const assets = [
  { name: 'Bitcoin / USDT', symbol: 'BINANCE:BTCUSDT', cls: 'Crypto' },
  { name: 'Hyperliquid / USDT', symbol: 'BYBIT:HYPEUSDT', cls: 'Crypto' }
];
const savedAssets = JSON.parse(localStorage.getItem('atlas.assets') || 'null');
let assets = Array.isArray(savedAssets) && savedAssets.length
  ? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))
  : defaultAssets;
"""
    patched = transform_app_js(rewritten)

    assert "HYPEUSDT" not in patched.upper()
    assert "BINANCE:BTCUSDT" in patched
    assert "CANONICAL_PRODUCTION_SYMBOLS.has(String(a.symbol || '').toUpperCase())" in patched


def test_hype_exposure_diagnostic_ignores_legacy_chart_conditional(tmp_path):
    # Render's legacy chart compatibility patch leaves HYPEUSDT inside a
    # conditional expression even though HYPE is no longer a selectable asset.
    # The runtime health flag must report actual asset exposure, not token text.
    app = """const defaultAssets = [
  { name: 'Bitcoin / USDT', symbol: 'BINANCE:BTCUSDT', cls: 'Crypto' }
];
const savedAssets = JSON.parse(localStorage.getItem('atlas.assets') || 'null');
let assets = Array.isArray(savedAssets) && savedAssets.length
  ? savedAssets.filter(a => a && a.cls === 'Crypto' && String(a.symbol || '').toUpperCase().endsWith('USDT'))
  : defaultAssets;
function openAsset(asset) {
  loadTradingView(asset.symbol==='BINANCE:HYPEUSDT'?'BYBIT:HYPEUSDT':asset.symbol);
}
"""
    (tmp_path / "app.js").write_text(app, encoding="utf-8")

    state = apply_canonical_asset_ui_patch(tmp_path)
    patched = (tmp_path / "app.js").read_text(encoding="utf-8")

    assert "HYPEUSDT" in patched.upper()  # compatibility token may remain
    assert state["hype_exposed"] is False
    assert state["count"] == 11
    assert state["saved_assets_filtered"] is True
    assert state["score_changed"] is False
    assert state["threshold_changed"] is False


def test_render_entrypoint_routes_through_canonical_universe_launcher():
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloud_start.py").read_text(encoding="utf-8")
    launcher = (root / "cloud_production_canonical.py").read_text(encoding="utf-8")

    assert 'cloud_production_canonical.py' in source
    assert 'enforce_production_asset_universe(atlas)' in launcher
    assert 'apply_canonical_asset_ui_patch(BASE)' in launcher
    assert 'cloud_web_only_final.py' in launcher


def test_consensus_shadow_workflow_uses_canonical_expanded_asset_universe():
    root = Path(__file__).resolve().parents[1]
    source = (root / ".github/workflows/consensus-tiebreak-shadow-prospective.yml").read_text(encoding="utf-8")
    expected = "BTCUSDT ETHUSDT SOLUSDT XRPUSDT BNBUSDT DOGEUSDT ZECUSDT ADAUSDT LINKUSDT AVAXUSDT LTCUSDT"

    assert f"symbols='{expected}'" in source
    assert "for s in $symbols; do" in source
    assert "HYPEUSDT" not in source
