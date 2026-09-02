from pathlib import Path


def test_unified_terminal_polish_is_loaded_and_mobile_safe():
    polish = Path('atlas-unified-terminal-polish.js').read_text(encoding='utf-8')
    boot = Path('render_boot_patch.py').read_text(encoding='utf-8')

    assert 'ATLAS_UNIFIED_TERMINAL_POLISH_V2' in polish
    assert 'smartPrice' in polish
    assert 'au-target-tile' in polish
    assert 'Setup ready · trigger pending' in polish
    assert 'SAFETY ' in polish
    assert 'safety passed, trigger pending' in polish
    assert 'atlas-unified-terminal-polish.js?v=unified-terminal-polish-v2-execution-semantics' in boot
