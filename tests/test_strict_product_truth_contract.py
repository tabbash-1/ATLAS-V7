from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_JS = 'ATLAS_UNIFIED_TERMINAL_V6_SINGLE_SNAPSHOT_HTF'
CURRENT_CACHE = 'unified-terminal-v6-single-snapshot-htf'
STALE_JS = 'ATLAS_UNIFIED_TERMINAL_V5_STRICT_FINAL_GATE'
STALE_CACHE = 'unified-terminal-v5-strict-final-gate'


def text(name):
    return (ROOT / name).read_text(encoding='utf-8')


def test_strict_smoke_and_render_boot_follow_current_terminal_contract():
    terminal = text('atlas-unified-terminal.js')
    smoke = text('.github/workflows/atlas-strict-product-truth-live-smoke.yml')
    boot = text('render_boot_patch.py')

    assert CURRENT_JS in terminal
    assert CURRENT_JS in smoke
    assert STALE_JS not in smoke
    assert CURRENT_CACHE in smoke
    assert CURRENT_CACHE in boot
    assert STALE_CACHE not in smoke
    assert STALE_CACHE not in boot

    assert "canonicalContract:'canonical_decision'" in text('atlas-production-decision.js')
    assert "sourceOfTruth:'FINAL_TRADE_GATE'" in text('atlas-production-decision.js')
    assert '/api/outcomes/summary?scope=signals&horizon=12' in text('atlas-paper-portfolio-ui.js')


if __name__ == '__main__':
    test_strict_smoke_and_render_boot_follow_current_terminal_contract()
    print('strict product truth contract tests: ok')
