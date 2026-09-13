from pathlib import Path


def test_cost_and_risk_helpers_not_wired_into_production_entrypoints():
    markers = ('atlas_execution_cost', 'atlas_risk_geometry', 'evaluate_execution_cost', 'size_position_from_stop')
    production_files = (
        'cloud_start.py',
        'cloud_web_only.py',
        'cloud_web_only_final.py',
        'final_trade_ready_guard.py',
    )
    for name in production_files:
        text = Path(name).read_text(encoding='utf-8')
        for marker in markers:
            assert marker not in text, f'{marker} unexpectedly wired into {name}'
