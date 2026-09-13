from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_TERMINAL_JS = 'ATLAS_UNIFIED_TERMINAL_V6_SINGLE_SNAPSHOT_HTF'
CURRENT_TERMINAL_CACHE = 'unified-terminal-v6-single-snapshot-htf'
STALE_TERMINAL_JS = 'ATLAS_UNIFIED_TERMINAL_V5_STRICT_FINAL_GATE'
STALE_TERMINAL_CACHE = 'unified-terminal-v5-strict-final-gate'
CURRENT_PRODUCTION_JS = 'ATLAS_PRODUCTION_DECISION_UI_V13_EXTENDED_TARGET_EVIDENCE'
CURRENT_PRODUCTION_CACHE = 'production-decision-v13-extended-target-evidence'
STALE_PRODUCTION_JS = 'ATLAS_PRODUCTION_DECISION_UI_V12_FINAL_GATE_ONLY'
STALE_PRODUCTION_CACHE = 'production-decision-v12-final-gate-only'


def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_strict_smoke_and_render_boot_follow_current_ui_contracts():
    terminal = text('atlas-unified-terminal.js')
    production = text('atlas-production-decision.js')
    smoke = text('.github/workflows/atlas-strict-product-truth-live-smoke.yml')
    boot = text('render_boot_patch.py')

    assert CURRENT_TERMINAL_JS in terminal
    assert CURRENT_TERMINAL_JS in smoke
    assert STALE_TERMINAL_JS not in smoke
    assert CURRENT_TERMINAL_CACHE in smoke
    assert CURRENT_TERMINAL_CACHE in boot
    assert STALE_TERMINAL_CACHE not in smoke
    assert STALE_TERMINAL_CACHE not in boot

    assert CURRENT_PRODUCTION_JS in production
    assert CURRENT_PRODUCTION_JS in smoke
    assert STALE_PRODUCTION_JS not in smoke
    assert CURRENT_PRODUCTION_CACHE in smoke
    assert CURRENT_PRODUCTION_CACHE in boot
    assert STALE_PRODUCTION_CACHE not in smoke
    assert STALE_PRODUCTION_CACHE not in boot

    assert "canonicalContract:'canonical_decision'" in production
    assert "sourceOfTruth:'FINAL_TRADE_GATE'" in production
    assert '/api/outcomes/summary?scope=signals&horizon=12' in text('atlas-paper-portfolio-ui.js')


if __name__ == '__main__':
    test_strict_smoke_and_render_boot_follow_current_ui_contracts()
    print('strict product truth contract tests: ok')
