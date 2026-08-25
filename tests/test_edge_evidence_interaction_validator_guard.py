from types import SimpleNamespace

import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_validator_guard as guard


def joint(status='DESIGN_READ_AVAILABLE', supported=True, horizons=None):
    if horizons is None:
        horizons = [1, 4, 12] if supported else []
    return {
        'report': {
            'version': 'J',
            'status': status,
            'future_interaction_validation_supported': supported,
            'horizons_with_sufficient_joint_coverage_h': horizons,
        }
    }


def manifest(horizons=None):
    return protocol.build_manifest(joint(horizons=horizons))


def test_valid_preregistered_protocol_and_unchanged_design_arms_guard_only():
    m = manifest()
    out = guard.evaluate(m, joint())
    assert out['status'] == 'VALIDATOR_ARMED'
    assert out['protocol_hash_verified'] is True
    assert out['protocol_status_preregistered'] is True
    assert out['current_joint_design_ready'] is True
    assert out['eligible_horizon_set_unchanged'] is True
    assert out['validator_execution_started'] is False
    assert out['outcomes_read'] is False
    assert out['interaction_outcome_testing_performed'] is False
    assert out['rule_selection_allowed'] is False
    assert out['grid_search_allowed'] is False
    assert out['horizon_selection_allowed'] is False
    assert out['interaction_filter_activation_allowed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False


def test_missing_protocol_is_blocked():
    out = guard.evaluate(None, joint())
    assert out['status'] == 'BLOCKED'
    assert out['protocol_hash_present'] is False
    assert 'MISSING_PROTOCOL_HASH' in out['blockers']
    assert 'PROTOCOL_NOT_PREREGISTERED' in out['blockers']


def test_tampered_protocol_hash_is_blocked():
    m = manifest()
    m['minimum_samples']['total_settled'] += 1
    out = guard.evaluate(m, joint())
    assert out['status'] == 'BLOCKED'
    assert out['protocol_hash_verified'] is False
    assert 'PROTOCOL_HASH_VERIFICATION_FAILED' in out['blockers']


def test_changed_eligible_horizon_set_is_blocked_even_with_valid_old_hash():
    m = manifest([1, 4, 12])
    out = guard.evaluate(m, joint(horizons=[1, 4]))
    assert out['status'] == 'BLOCKED'
    assert out['protocol_hash_verified'] is True
    assert out['eligible_horizon_set_unchanged'] is False
    assert 'ELIGIBLE_HORIZON_SET_CHANGED_SINCE_PREREGISTRATION' in out['blockers']


def test_new_horizon_appearing_after_registration_is_also_blocked():
    m = manifest([1, 4])
    out = guard.evaluate(m, joint(horizons=[1, 4, 12]))
    assert out['status'] == 'BLOCKED'
    assert out['eligible_horizon_set_unchanged'] is False
    assert 'ELIGIBLE_HORIZON_SET_CHANGED_SINCE_PREREGISTRATION' in out['blockers']


def test_current_design_not_ready_is_blocked():
    m = manifest()
    out = guard.evaluate(m, joint('SPARSE_INTERACTION_DESIGN', False, []))
    assert out['status'] == 'BLOCKED'
    assert out['current_joint_design_ready'] is False
    assert 'CURRENT_JOINT_COVERAGE_DESIGN_NOT_READY' in out['blockers']


def test_blocked_protocol_manifest_cannot_arm_guard():
    blocked_manifest = protocol.build_manifest(joint('COLLECTING', False, []))
    out = guard.evaluate(blocked_manifest, joint())
    assert out['status'] == 'BLOCKED'
    assert out['protocol_hash_verified'] is True
    assert out['protocol_status_preregistered'] is False
    assert 'PROTOCOL_NOT_PREREGISTERED' in out['blockers']


def test_install_is_read_only_refreshable_and_idempotent():
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    pstate = {'manifest': manifest()}
    collector = SimpleNamespace(
        production_decision=decision,
        forward_observe=forward,
        EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE=pstate,
        EDGE_EVIDENCE_JOINT_COVERAGE_STATE=joint(),
    )
    first = guard.install(collector)
    assert first['report']['status'] == 'VALIDATOR_ARMED'
    assert first['report']['validator_execution_started'] is False
    assert collector.production_decision is decision
    assert collector.forward_observe is forward

    collector.EDGE_EVIDENCE_JOINT_COVERAGE_STATE = joint(horizons=[1, 4])
    refreshed = collector.edge_evidence_interaction_validator_guard_refresh()
    assert refreshed['status'] == 'BLOCKED'
    assert refreshed['outcomes_read'] is False
    assert collector.production_decision is decision
    assert collector.forward_observe is forward

    second = guard.install(collector)
    assert second is first
