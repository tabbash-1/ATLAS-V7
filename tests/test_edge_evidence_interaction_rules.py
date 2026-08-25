from pathlib import Path
from types import SimpleNamespace

import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules


def joint(horizons=None):
    return {
        'report': {
            'version': 'J',
            'status': 'DESIGN_READ_AVAILABLE',
            'future_interaction_validation_supported': True,
            'horizons_with_sufficient_joint_coverage_h': horizons or [1, 4, 12],
        }
    }


def pmanifest(horizons=None):
    return protocol.build_manifest(joint(horizons))


def test_single_semantic_rule_is_fixed_before_outcomes():
    p = pmanifest()
    out = rules.build_manifest(p)
    assert out['status'] == 'PREREGISTERED'
    assert out['parent_protocol_hash'] == p['protocol_hash']
    assert out['rule_count'] == 1
    assert out['eligible_volatility_horizons_h'] == [1, 4, 12]
    rule = out['rules'][0]
    assert rule['rule_id'] == rules.RULE_ID
    assert rule['profit_regime_relation_equals'] == 'REGIME_ALIGNED'
    assert rule['microstructure_relation_to_signal_equals'] == 'ALIGNED'
    assert rule['volatility_target_fit_equals'] == 'PLAUSIBLE_VS_EMPIRICAL_P80'
    assert rule['volatility_stop_fit_equals'] == 'PLAUSIBLE_VS_EMPIRICAL_P80'
    assert rule['apply_identically_to_every_eligible_horizon'] is True
    assert out['rule_selection_after_outcomes_allowed'] is False
    assert out['alternative_rule_search_allowed'] is False
    assert out['grid_search_allowed'] is False
    assert out['horizon_selection_allowed'] is False
    assert out['outcomes_read'] is False
    assert rules.verify_manifest(out, p) is True


def test_rule_tampering_breaks_hash():
    p = pmanifest()
    out = rules.build_manifest(p)
    out['rules'][0]['microstructure_relation_to_signal_equals'] = 'MIXED_OR_INSUFFICIENT'
    assert rules.verify_manifest(out, p) is False


def test_parent_protocol_hash_mismatch_is_rejected():
    p1 = pmanifest([1, 4, 12])
    p2 = pmanifest([1, 4])
    out = rules.build_manifest(p1)
    assert rules.verify_manifest(out, p2) is False


def test_blocked_parent_protocol_cannot_register_rules():
    blocked = protocol.build_manifest({
        'report': {
            'version': 'J',
            'status': 'COLLECTING',
            'future_interaction_validation_supported': False,
            'horizons_with_sufficient_joint_coverage_h': [],
        }
    })
    out = rules.build_manifest(blocked)
    assert out['status'] == 'BLOCKED_BY_PROTOCOL'
    assert 'PARENT_PROTOCOL_NOT_READY' in out['blockers']


def _collector(tmp_path, p):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    c = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=decision,
        forward_observe=forward,
        EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE={'manifest': p},
    )
    return c, decision, forward


def test_persistent_rules_survive_restart_and_parent_change_is_detected(tmp_path):
    p1 = pmanifest([1, 4, 12])
    c1, decision, forward = _collector(tmp_path, p1)
    first = rules.install(c1)
    assert first['registration_locked'] is True
    frozen_hash = first['manifest']['rules_hash']
    assert (tmp_path / rules.REGISTRATION_FILENAME).exists()
    assert c1.production_decision is decision
    assert c1.forward_observe is forward

    # Restart with a different protocol must not silently rewrite the rules.
    p2 = pmanifest([1, 4])
    c2, _, _ = _collector(tmp_path, p2)
    second = rules.install(c2)
    assert second['registration_locked'] is True
    assert second['manifest']['status'] == 'REGISTRATION_CORRUPT'
    assert second['manifest']['rules_hash'] is None
    assert second['persistence_error'] == 'RULE_REGISTRATION_HASH_OR_PARENT_INVALID'

    # The persisted bytes remain the original preregistration.
    raw = (tmp_path / rules.REGISTRATION_FILENAME).read_text(encoding='utf-8')
    assert frozen_hash in raw


def test_install_without_data_is_process_local_frozen_and_idempotent():
    p = pmanifest()
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    c = SimpleNamespace(
        production_decision=decision,
        forward_observe=forward,
        EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE={'manifest': p},
    )
    first = rules.install(c)
    assert first['registration_locked'] is True
    assert first['manifest']['status'] == 'PREREGISTERED'
    second = rules.install(c)
    assert second is first
    assert c.production_decision is decision
    assert c.forward_observe is forward
