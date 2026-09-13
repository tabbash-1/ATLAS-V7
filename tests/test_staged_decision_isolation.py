from pathlib import Path


def test_staged_module_is_not_wired_into_production_entrypoints():
    forbidden = ('atlas_decision_architecture', 'evaluate_staged_decision')
    production_files = (
        'cloud_start.py',
        'cloud_web_only.py',
        'cloud_web_only_final.py',
        'final_trade_ready_guard.py',
    )
    for name in production_files:
        text = Path(name).read_text(encoding='utf-8')
        for marker in forbidden:
            assert marker not in text, f'{marker} unexpectedly wired into {name}'
