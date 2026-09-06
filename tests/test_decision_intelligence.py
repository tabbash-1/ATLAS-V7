import copy

from decision_intelligence import VERSION, build


def _row(**overrides):
    row = {
        'candidate_direction': 'LONG',
        'setup_quality_gate': {'status': 'PASS', 'reason': 'SETUP_NOT_IN_EVIDENCE_QUARANTINE'},
        'data_degraded': False,
    }
    row.update(overrides)
    return row


def _out(**overrides):
    out = {
        'decision': 'WAIT',
        'analysis_ready': False,
        'confidence': 65,
        'signal_threshold': 68,
        'candidate_plan': {'direction': 'LONG', 'risk_reward': 2.0},
        'geometry_readiness': {'ready': True, 'qualified': True, 'blocker_codes': [], 'checks': {'entry': True, 'stop': True, 'target': True}},
        'evidence_profile': {'warnings': [], 'confirmations': ['STRUCTURAL_ROOM_CONFIRMED']},
        'what_changes_status': ['BREAKOUT_CONFIRMATION_REQUIRED'],
        'setup_quality_gate': {'status': 'PASS'},
    }
    out.update(overrides)
    return out


def test_shadow_layer_never_mutates_inputs_or_overrides_production():
    row = _row()
    out = _out()
    before = copy.deepcopy((row, out))
    result = build(row, out)
    assert (row, out) == before
    assert result['version'] == VERSION
    assert result['mode'] == 'SHADOW_EXPLANATION_ONLY'
    assert result['can_override_canonical_decision'] is False
    assert result['can_change_score'] is False
    assert result['can_change_threshold'] is False
    assert result['can_change_geometry'] is False
    assert result['analysis_only'] is True
    assert result['live_execution'] is False


def test_trade_ready_requires_canonical_trade_and_clear_hard_blockers():
    out = _out(decision='LONG', analysis_ready=True, confidence=82)
    result = build(_row(), out)
    assert result['canonical_decision'] == 'LONG'
    assert result['stage'] == 'TRADE_READY'
    assert result['hard_blockers'] == []
    assert result['execution_quality'] == 100.0


def test_near_threshold_geometry_ready_setup_is_forming_not_promoted():
    result = build(_row(), _out(confidence=64, signal_threshold=68))
    assert result['canonical_decision'] == 'WAIT'
    assert result['stage'] == 'SETUP_FORMING'
    assert result['candidate_direction'] == 'LONG'
    assert result['score_margin'] == -4.0
    assert result['can_override_canonical_decision'] is False


def test_geometry_failure_is_explicit_hard_blocker():
    out = _out(geometry_readiness={
        'ready': False,
        'blocker_codes': ['RR_BELOW_MIN'],
        'checks': {'entry': True, 'stop': True, 'target': False},
    })
    result = build(_row(), out)
    assert result['stage'] == 'WATCH'
    assert 'GEOMETRY_RR_BELOW_MIN' in result['hard_blockers']
    assert result['execution_quality'] < 100
    assert result['next_requirement'] == 'CLEAR_GEOMETRY_RR_BELOW_MIN'


def test_quarantined_setup_is_explained_not_repromoted():
    gate = {'status': 'BLOCK', 'reason': '4_12H_SETUP_FAMILY_FAILED_FORWARD_EVIDENCE_GATE'}
    out = _out(confidence=90, setup_quality_gate=gate)
    result = build(_row(setup_quality_gate=gate), out)
    assert result['canonical_decision'] == 'WAIT'
    assert '4_12H_SETUP_FAMILY_FAILED_FORWARD_EVIDENCE_GATE' in result['hard_blockers']
    assert result['can_override_canonical_decision'] is False
