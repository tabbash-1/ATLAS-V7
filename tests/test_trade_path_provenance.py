import trade_path_settlement as path


def _row(**extra):
    base = {
        'id': 'obs-1',
        'captured_at': '2026-08-29T00:00:00+03:00',
        'captured_at_ms': 1000,
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100.0,
        'final_score': 80,
        'production_signal_qualified': True,
        'research_champion_take': True,
        'scoring_version': 'SCORE_V6',
        'decision_version': 'DECISION_V3',
        'trade_plan_version': 'PLAN_V2',
        'policy_version': 'POLICY_V1',
        'generation_id': 'gen-1',
    }
    base.update(extra)
    return base


def _geometry_record(**extra):
    base = {
        'geometry_generation': 'GEOM_V4',
        'geometry': {
            'entry': 100.0,
            'stop_loss': 99.0,
            'tp1': 101.0,
            'tp2': 102.0,
            'rr_tp2': 2.0,
            'direction': 'LONG',
            'geometry_version': 'GEOM_V4',
        },
    }
    base.update(extra)
    return base


def test_path_outcome_preserves_forward_provenance():
    x = path.settle_row(_row(), _geometry_record(), now_ms=1000)
    assert x['scoring_version'] == 'SCORE_V6'
    assert x['decision_version'] == 'DECISION_V3'
    assert x['trade_plan_version'] == 'PLAN_V2'
    assert x['policy_version'] == 'POLICY_V1'
    assert x['generation_id'] == 'gen-1'
    assert x['geometry_generation'] == 'GEOM_V4'


def test_path_outcome_can_fallback_to_frozen_geometry_provenance():
    r = _row(
        scoring_version=None,
        decision_version=None,
        trade_plan_version=None,
        policy_version=None,
        generation_id=None,
    )
    g = _geometry_record(
        scoring_version='FROZEN_SCORE_V6',
        decision_version='FROZEN_DECISION_V3',
        trade_plan_version='FROZEN_PLAN_V2',
        policy_version='FROZEN_POLICY_V1',
        generation_id='frozen-gen-1',
    )
    x = path.settle_row(r, g, now_ms=1000)
    assert x['scoring_version'] == 'FROZEN_SCORE_V6'
    assert x['decision_version'] == 'FROZEN_DECISION_V3'
    assert x['trade_plan_version'] == 'FROZEN_PLAN_V2'
    assert x['policy_version'] == 'FROZEN_POLICY_V1'
    assert x['generation_id'] == 'frozen-gen-1'


if __name__ == '__main__':
    test_path_outcome_preserves_forward_provenance()
    test_path_outcome_can_fallback_to_frozen_geometry_provenance()
    print('trade path provenance tests: ok')
