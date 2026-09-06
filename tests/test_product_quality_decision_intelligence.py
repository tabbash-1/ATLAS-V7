import types

import product_quality_gate_overlay as gate


def _production_row():
    return {
        'ok': True,
        'symbol': 'BTCUSDT',
        'candidate_direction': 'LONG',
        'actionable_decision': 'LONG',
        'actionable_reason': 'PRODUCTION_SIGNAL_QUALIFIED',
        'production_signal_qualified': True,
        'analysis_ready': True,
        'setup_ready': True,
        'score': 82.0,
        'signal_threshold': 68.0,
        'regime': 'RANGE',
        'playbook': 'BREAKOUT_LONG',
        'relative_volume': 1.3,
        'futures_available': True,
        'score_attribution': {'futures_reason': 'ALIGNED', 'obstacle_reason': 'CLEAR_SPACE_TO_PRIOR_STRUCTURE'},
        'geometry_gate': {
            'qualified': True,
            'status': 'PASS',
            'reason': 'GEOMETRY_VALID',
            'primary_blocker': None,
            'blocker_codes': [],
            'checks': {'entry_valid': True, 'stop_valid': True, 'target_valid': True, 'rr_valid': True},
            'reason_schema_version': 'ATLAS_GEOMETRY_REASON_CODES_V1',
            'version': 'ATLAS_CANONICAL_GEOMETRY_TRUTH_V1',
        },
        'trade_plan': {
            'entry': 100.0,
            'stop_loss': 98.0,
            'tp1': 102.0,
            'tp2': 104.0,
            'rr_tp2': 2.0,
            'entry_trigger': 'VERIFIED_BREAKOUT',
            'invalidation': 'STRUCTURE_FAILS',
            'geometry_provenance': {
                'geometry_version': 'ATLAS_GEOMETRY_V5_ATR_STRUCTURE_PROVENANCE',
                'entry_basis': 'TEST', 'stop_basis': 'TEST', 'tp1_basis': 'TEST', 'tp2_basis': 'TEST',
            },
        },
    }


def test_installed_layer_preserves_score_threshold_decision_and_geometry():
    raw = _production_row()
    atlas = types.SimpleNamespace(production_decision=lambda symbol: dict(raw))
    state = gate.install(atlas)
    out = atlas.production_decision('BTCUSDT')

    assert out['score'] == raw['score']
    assert out['signal_threshold'] == raw['signal_threshold']
    assert out['production_signal_qualified'] is True
    assert out['canonical_product_decision'] == 'LONG'
    assert out['analyst_output']['decision'] == 'LONG'
    assert out['analyst_output']['entry'] == 100.0
    assert out['analyst_output']['stop_loss'] == 98.0
    assert out['analyst_output']['take_profit'] == 104.0
    assert out['analyst_output']['risk_reward'] == 2.0

    intelligence = out['decision_intelligence']
    assert intelligence is out['analyst_output']['decision_intelligence']
    assert intelligence['stage'] == 'TRADE_READY'
    assert intelligence['can_override_canonical_decision'] is False
    assert intelligence['can_change_score'] is False
    assert intelligence['can_change_threshold'] is False
    assert intelligence['can_change_geometry'] is False
    assert state['decision_intelligence_shadow_only'] is True
    assert state['decision_intelligence_can_override'] is False


def test_quarantine_still_has_authority_over_shadow_intelligence():
    raw = _production_row()
    raw['regime'] = 'TREND_UP'
    raw['playbook'] = 'TREND_PULLBACK_LONG'
    atlas = types.SimpleNamespace(production_decision=lambda symbol: dict(raw))
    gate.install(atlas)
    out = atlas.production_decision('BTCUSDT')

    assert out['pre_quality_gate_actionable_decision'] == 'LONG'
    assert out['canonical_product_decision'] == 'WAIT'
    assert out['analyst_output']['decision'] == 'WAIT'
    assert out['decision_intelligence']['canonical_decision'] == 'WAIT'
    assert out['decision_intelligence']['can_override_canonical_decision'] is False
    assert '4_12H_SETUP_FAMILY_FAILED_FORWARD_EVIDENCE_GATE' in out['decision_intelligence']['hard_blockers']
