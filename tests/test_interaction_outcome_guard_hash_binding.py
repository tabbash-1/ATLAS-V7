import edge_evidence_interaction_outcome_validator as validator
import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules
import edge_evidence_interaction_validator_guard as guard


def _joint():
    return {
        'report': {
            'version': 'J',
            'status': 'DESIGN_READ_AVAILABLE',
            'future_interaction_validation_supported': True,
            'horizons_with_sufficient_joint_coverage_h': [1, 4, 12],
        }
    }


def test_stale_or_foreign_armed_guard_cannot_read_outcomes():
    p = protocol.build_manifest(_joint())
    r = rules.build_manifest(p)
    g = guard.evaluate(p, _joint())
    assert g['status'] == 'VALIDATOR_ARMED'
    g['armed_protocol_hash'] = 'foreign-protocol-hash'

    called = {'n': 0}

    def forbidden_loader():
        called['n'] += 1
        raise AssertionError('outcome loader must remain unreachable')

    out = validator.validate(p, g, r, [], [], [], forbidden_loader)
    assert out['status'] == 'BLOCKED'
    assert 'GUARD_PROTOCOL_HASH_MISMATCH' in out['blockers']
    assert out['validator_execution_started'] is False
    assert out['outcomes_read'] is False
    assert called['n'] == 0
