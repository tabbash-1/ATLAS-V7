import json
import tempfile
from pathlib import Path

import scenario_evidence_pipeline as p


def decision(readiness='CONDITIONAL_SCENARIO_READY', direction='LONG'):
    return {
        'ok': True, 'symbol': 'BTCUSDT', 'score': 74, 'threshold': 68,
        'actionable_decision': 'WAIT', 'canonical_product_decision': 'WAIT',
        'analysis_ready': True, 'setup_ready': False,
        'htf_scenario_engine': {
            'version': 'HTF_SCENARIO_ENGINE_V1', 'readiness': readiness,
            'reason': 'HTF_THESIS_AND_PRICE_ACTION_COMPATIBLE',
            'htf_thesis_status': 'PASS', 'htf_thesis_direction': direction,
            'price_action_status': 'BULLISH_CONFLUENCE' if direction == 'LONG' else 'BEARISH_CONFLUENCE',
            'selected_case': {
                'direction': direction,
                'trigger_type': 'BREAKOUT_RETEST_HOLD' if direction == 'LONG' else 'BREAKDOWN_RETEST_FAIL',
                'trigger_level': 100.0,
                'invalidation_level': 90.0 if direction == 'LONG' else 110.0,
            },
        },
    }


def test_capture_only_conditional_ready():
    row = p.capture_from_decision(decision(), '2026-09-06T00:00:00+00:00')
    assert row and row['scenario_id']
    assert row['frozen_context']['score'] == 74
    assert p.capture_from_decision(decision('WAIT_FOR_HTF_ALIGNMENT'), '2026-09-06T00:00:00+00:00') is None


def test_dedupe_stable_for_same_frozen_geometry():
    a = p.capture_from_decision(decision(), '2026-09-06T00:00:00+00:00')
    b = p.capture_from_decision(decision(), '2026-09-06T01:00:00+00:00')
    rows = []
    assert p.dedupe_append(rows, a) is True
    assert p.dedupe_append(rows, b) is False
    assert len(rows) == 1


def test_scenario_key_changes_with_geometry():
    a = p.capture_from_decision(decision(), '2026-09-06T00:00:00+00:00')
    d = decision()
    d['htf_scenario_engine']['selected_case']['trigger_level'] = 101.0
    b = p.capture_from_decision(d, '2026-09-06T01:00:00+00:00')
    assert a['scenario_id'] != b['scenario_id']


def test_save_is_research_only_and_has_all_horizons():
    row = p.capture_from_decision(decision(), '2026-09-06T00:00:00+00:00')
    snap = p.calibration_snapshot([row], '2026-09-06T01:00:00+00:00')
    with tempfile.TemporaryDirectory() as td:
        p.save([row], snap, td)
        out = json.loads((Path(td) / 'scenario-outcomes.json').read_text())
        cal = json.loads((Path(td) / 'scenario-calibration-latest.json').read_text())
        assert out['research_only'] is True and out['live_execution'] is False
        assert set(cal['horizons']) == {'4', '8', '12'}
        assert cal['production_changed'] is False
        assert (Path(td) / 'history' / 'scenario-calibration.jsonl').exists()


def test_short_calibration_normalizes_raw_return_once():
    row = p.capture_from_decision(decision(direction='SHORT'), '2026-09-06T00:00:00+00:00')
    row.update({'triggered': True, 'triggered_at': '2026-09-06T04:00:00+00:00', 'activation_price': 100.0,
                'forward_return_pct': {'4': -5.0}})
    snap = p.calibration_snapshot([row], '2026-09-06T09:00:00+00:00')
    assert snap['horizons']['4']['overall_triggered']['avg_directional_return_pct'] == 5.0
    assert snap['horizons']['4']['overall_triggered']['wins'] == 1


if __name__ == '__main__':
    test_capture_only_conditional_ready()
    test_dedupe_stable_for_same_frozen_geometry()
    test_scenario_key_changes_with_geometry()
    test_save_is_research_only_and_has_all_horizons()
    test_short_calibration_normalizes_raw_return_once()
    print('scenario evidence pipeline tests: OK')
