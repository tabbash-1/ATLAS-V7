from pathlib import Path


def test_unified_terminal_polish_is_loaded_and_mobile_safe():
    polish = Path('atlas-unified-terminal-polish.js').read_text(encoding='utf-8')
    boot = Path('render_boot_patch.py').read_text(encoding='utf-8')

    assert 'ATLAS_UNIFIED_TERMINAL_POLISH_V4_WAIT_CAUSE' in polish
    assert 'smartPrice' in polish
    assert 'au-target-tile' in polish
    assert 'Canonical qualification must become YES' in polish
    assert 'Entry / Stop / Target geometry must become valid' in polish
    assert 'atlas-unified-terminal-polish.js?v=unified-terminal-polish-v4-wait-cause' in boot
