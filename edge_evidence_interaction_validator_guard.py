"""ATLAS interaction validator guard.

Fail-closed authorization layer for any future cross-layer outcome validator.
This module never reads outcomes and never executes validation. It only verifies
that the preregistered protocol is intact, currently PREREGISTERED, and still
compatible with the current outcome-free joint-coverage design.
"""

from __future__ import annotations

from copy import deepcopy

import edge_evidence_interaction_protocol as protocol

VERSION = 'EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_V1_FAIL_CLOSED'


def _joint_report(joint_state):
    if not isinstance(joint_state, dict):
        return {}
    report = joint_state.get('report')
    return report if isinstance(report, dict) else joint_state


def evaluate(manifest=None, joint_coverage_state=None):
    manifest = deepcopy(manifest) if isinstance(manifest, dict) else {}
    joint = _joint_report(joint_coverage_state)
    blockers = []

    hash_present = bool(manifest.get('protocol_hash'))
    hash_verified = bool(hash_present and protocol.verify_manifest(manifest))
    preregistered = manifest.get('status') == 'PREREGISTERED'
    design_ready = bool(
        joint.get('status') == 'DESIGN_READ_AVAILABLE'
        and joint.get('future_interaction_validation_supported') is True
    )

    registered_horizons = sorted({int(x) for x in (manifest.get('eligible_volatility_horizons_h') or [])})
    current_horizons = sorted({int(x) for x in (joint.get('horizons_with_sufficient_joint_coverage_h') or [])})
    horizon_set_unchanged = bool(registered_horizons and registered_horizons == current_horizons)

    if not hash_present:
        blockers.append('MISSING_PROTOCOL_HASH')
    elif not hash_verified:
        blockers.append('PROTOCOL_HASH_VERIFICATION_FAILED')
    if not preregistered:
        blockers.append('PROTOCOL_NOT_PREREGISTERED')
    if not design_ready:
        blockers.append('CURRENT_JOINT_COVERAGE_DESIGN_NOT_READY')
    if not registered_horizons:
        blockers.append('NO_PREREGISTERED_ELIGIBLE_HORIZONS')
    if registered_horizons != current_horizons:
        blockers.append('ELIGIBLE_HORIZON_SET_CHANGED_SINCE_PREREGISTRATION')

    armed = bool(
        hash_verified
        and preregistered
        and design_ready
        and horizon_set_unchanged
        and not blockers
    )

    return {
        'version': VERSION,
        'status': 'VALIDATOR_ARMED' if armed else 'BLOCKED',
        'protocol_hash_required': True,
        'protocol_hash_present': hash_present,
        'protocol_hash_verified': hash_verified,
        'protocol_status_preregistered': preregistered,
        'current_joint_design_ready': design_ready,
        'registered_eligible_horizons_h': registered_horizons,
        'current_eligible_horizons_h': current_horizons,
        'eligible_horizon_set_unchanged': horizon_set_unchanged,
        'protocol_mutation_allowed': False,
        'rule_selection_allowed': False,
        'adaptive_rule_search_allowed': False,
        'grid_search_allowed': False,
        'threshold_tuning_allowed': False,
        'horizon_selection_allowed': False,
        'outcomes_read': False,
        'validator_execution_started': False,
        'interaction_outcome_testing_performed': False,
        'performance_metrics_computed': False,
        'cross_layer_interaction_filtering_enabled': False,
        'interaction_filter_activation_allowed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'research_only': True,
        'blockers': blockers,
    }


def from_collector(collector):
    protocol_state = getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', None)
    manifest = protocol_state.get('manifest') if isinstance(protocol_state, dict) else None
    joint_state = getattr(collector, 'EDGE_EVIDENCE_JOINT_COVERAGE_STATE', None)
    return evaluate(manifest, joint_state)


def install(collector):
    if getattr(collector, '_EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE', {})

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    state = {
        'enabled': True,
        'version': VERSION,
        'read_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'report': from_collector(collector),
    }

    def refresh():
        state['report'] = from_collector(collector)
        return state['report']

    collector.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE = state
    collector.edge_evidence_interaction_validator_guard_refresh = refresh
    collector._EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('interaction validator guard mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('interaction validator guard mutated forward_observe')
    return state
