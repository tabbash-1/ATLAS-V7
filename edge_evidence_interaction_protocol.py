"""ATLAS preregistered cross-layer interaction validation protocol.

This module freezes the design of a possible future interaction study BEFORE any
interaction outcome analysis is allowed. It consumes only the outcome-free joint
coverage audit and produces a deterministic protocol manifest + hash.

Registration is one-way. While joint coverage is not ready, the candidate may
remain BLOCKED_BY_DESIGN. The first PREREGISTERED manifest is then frozen and,
when collector.DATA is available, persisted atomically so process restarts load
the exact same registration instead of silently re-registering a changed design.
A present but corrupt registration is never overwritten automatically.

It does not read outcomes, select profitable cells, search parameters, choose a
single volatility horizon, activate filters, assign weights, create composite
scores, or change Production. Any later interaction validator must prove it is
executing this exact protocol hash.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import edge_evidence_joint_coverage

VERSION = 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_V2_PERSISTENT_PREREGISTRATION'
PROTOCOL_SCHEMA = 'ATLAS_INTERACTION_VALIDATION_PROTOCOL_V1'
REGISTRATION_FILENAME = 'interaction_validation_preregistration.json'

# Frozen design constants. Changing any of these changes protocol_hash.
CHRONOLOGICAL_FOLDS = 3
MIN_TOTAL_SETTLED = 60
MIN_CELL_SETTLED_PER_FOLD = 5
MIN_TOTAL_SETTLED_PER_CELL = 20
MIN_BASELINE_SETTLED_PER_FOLD = 15
PRIMARY_METRIC = 'AVERAGE_R_DELTA_VS_CANONICAL_PRODUCTION_BASELINE'
SECONDARY_METRICS = (
    'WIN_RATE_DELTA_VS_BASELINE',
    'MAX_DRAWDOWN_R_DELTA_VS_BASELINE',
    'MEDIAN_R_DELTA_VS_BASELINE',
)
ALLOWED_PROFIT_VARIABLE = 'PROFIT_REGIME_RELATION'
ALLOWED_MICROSTRUCTURE_VARIABLE = 'MICROSTRUCTURE_RELATION_TO_SIGNAL'
ALLOWED_VOLATILITY_VARIABLES = (
    'VOLATILITY_TARGET_FIT',
    'VOLATILITY_STOP_FIT',
)


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _protocol_hash(manifest_without_hash):
    raw = _canonical_json(manifest_without_hash).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _eligible_horizons(joint_report):
    values = joint_report.get('horizons_with_sufficient_joint_coverage_h') or []
    return sorted({int(x) for x in values if int(x) in edge_evidence_joint_coverage.VOLATILITY_HORIZONS_H})


def build_manifest(joint_coverage_state=None):
    state = joint_coverage_state if isinstance(joint_coverage_state, dict) else {}
    joint = state.get('report') if isinstance(state.get('report'), dict) else state
    if not isinstance(joint, dict):
        joint = {}

    eligible = _eligible_horizons(joint)
    design_supported = bool(
        joint.get('status') == 'DESIGN_READ_AVAILABLE'
        and joint.get('future_interaction_validation_supported') is True
        and eligible
    )

    manifest = {
        'schema': PROTOCOL_SCHEMA,
        'version': VERSION,
        'status': 'PREREGISTERED' if design_supported else 'BLOCKED_BY_DESIGN',
        'joint_coverage_source_version': joint.get('version'),
        'joint_coverage_status_at_registration': joint.get('status') or 'UNAVAILABLE',
        'eligible_volatility_horizons_h': eligible,
        'all_eligible_horizons_must_be_reported_separately': True,
        'single_horizon_selection_allowed': False,
        'chosen_trade_horizon_assumed': False,
        'allowed_predictor_variables': {
            'profit_engine': [ALLOWED_PROFIT_VARIABLE],
            'microstructure': [ALLOWED_MICROSTRUCTURE_VARIABLE],
            'volatility_per_horizon': list(ALLOWED_VOLATILITY_VARIABLES),
        },
        'shared_production_fields_forbidden_as_interaction_predictors': [
            'direction', 'entry', 'score', 'signal_threshold'
        ],
        'baseline': {
            'type': 'CANONICAL_PRODUCTION_EXECUTION_COHORT',
            'same_forward_id_universe_required': True,
            'same_settlement_engine_required': True,
        },
        'split_policy': {
            'type': 'CHRONOLOGICAL_NON_SHUFFLED_FOLDS',
            'fold_count': CHRONOLOGICAL_FOLDS,
            'shuffle_allowed': False,
            'future_information_in_training_allowed': False,
        },
        'minimum_samples': {
            'total_settled': MIN_TOTAL_SETTLED,
            'cell_settled_per_fold': MIN_CELL_SETTLED_PER_FOLD,
            'total_settled_per_cell': MIN_TOTAL_SETTLED_PER_CELL,
            'baseline_settled_per_fold': MIN_BASELINE_SETTLED_PER_FOLD,
        },
        'metrics': {
            'primary': PRIMARY_METRIC,
            'secondary': list(SECONDARY_METRICS),
            'primary_metric_must_be_positive_in_every_fold': True,
            'drawdown_must_not_worsen_in_any_fold': True,
        },
        'multiple_testing_policy': {
            'cell_rules_must_be_declared_before_outcomes': True,
            'adaptive_rule_search_allowed': False,
            'grid_search_allowed': False,
            'threshold_tuning_after_outcomes_allowed': False,
            'best_cell_selection_after_outcomes_allowed': False,
            'horizon_selection_after_outcomes_allowed': False,
        },
        'validation_policy': {
            'all_folds_must_pass': True,
            'pooled_success_cannot_override_failed_fold': True,
            'missing_fold_is_failure': True,
            'insufficient_cell_is_excluded_not_merged': True,
            'future_validator_must_match_protocol_hash': True,
        },
        'outcomes_read': False,
        'interaction_outcome_testing_performed': False,
        'performance_metrics_computed': False,
        'rules_searched': False,
        'grid_search_performed': False,
        'weights_assigned': False,
        'composite_trade_score_created': False,
        'cross_layer_interaction_filtering_enabled': False,
        'interaction_filter_activation_allowed': False,
        'gate_promoted': False,
        'can_override_production': False,
        'production_ready_claimed': False,
        'live_trading_ready_claimed': False,
        'historical_features_recomputed': False,
        'research_only': True,
        'blockers': [] if design_supported else ['JOINT_COVERAGE_DESIGN_NOT_READY'],
    }
    manifest['protocol_hash'] = _protocol_hash(manifest)
    return manifest


def verify_manifest(manifest):
    if not isinstance(manifest, dict):
        return False
    expected = manifest.get('protocol_hash')
    if not expected:
        return False
    payload = dict(manifest)
    payload.pop('protocol_hash', None)
    return expected == _protocol_hash(payload)


def _registration_file(collector):
    data = getattr(collector, 'DATA', None)
    if data is None:
        return None
    return Path(data) / REGISTRATION_FILENAME


def _load_registration(path):
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as exc:
        return None, f'{type(exc).__name__}: {exc}'
    if not isinstance(raw, dict):
        return None, 'REGISTRATION_NOT_JSON_OBJECT'
    if raw.get('status') != 'PREREGISTERED':
        return raw, 'REGISTRATION_STATUS_NOT_PREREGISTERED'
    if not verify_manifest(raw):
        return raw, 'REGISTRATION_HASH_INVALID'
    return raw, None


def _atomic_write_registration(path, manifest):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(_canonical_json(manifest) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def install(collector):
    """Expose a one-way frozen protocol state; never wrap Production or Forward."""
    if getattr(collector, '_EDGE_EVIDENCE_INTERACTION_PROTOCOL_INSTALLED', False):
        return getattr(collector, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE', {})

    original_decision = getattr(collector, 'production_decision', None)
    original_forward = getattr(collector, 'forward_observe', None)
    registration_file = _registration_file(collector)
    joint_state = getattr(collector, 'EDGE_EVIDENCE_JOINT_COVERAGE_STATE', None)

    manifest = None
    registration_locked = False
    persistence_error = None

    if registration_file is not None and registration_file.exists():
        loaded, load_error = _load_registration(registration_file)
        registration_locked = True  # A present registration is never auto-overwritten.
        if loaded is not None:
            manifest = loaded
        else:
            manifest = {
                'status': 'REGISTRATION_CORRUPT',
                'protocol_hash': None,
                'eligible_volatility_horizons_h': [],
                'blockers': ['PERSISTED_PREREGISTRATION_UNREADABLE'],
            }
        persistence_error = load_error
    else:
        candidate = build_manifest(joint_state)
        manifest = candidate
        if candidate.get('status') == 'PREREGISTERED':
            if registration_file is not None:
                try:
                    _atomic_write_registration(registration_file, candidate)
                except Exception as exc:
                    # Fail closed: do not call this registration locked if persistence failed.
                    persistence_error = f'{type(exc).__name__}: {exc}'
                else:
                    registration_locked = True
            else:
                # Test/lightweight collectors without DATA still get process-local freezing.
                registration_locked = True

    state = {
        'enabled': True,
        'version': VERSION,
        'read_only': True,
        'wraps_production_decision': False,
        'wraps_forward_observe': False,
        'can_override_production': False,
        'registration_file': str(registration_file) if registration_file is not None else None,
        'registration_locked': registration_locked,
        'persistence_error': persistence_error,
        'manifest': manifest,
    }

    def refresh():
        # Once registered, NEVER rebuild from current joint coverage.
        if state['registration_locked']:
            if registration_file is not None:
                loaded, load_error = _load_registration(registration_file)
                state['persistence_error'] = load_error
                if loaded is not None:
                    state['manifest'] = loaded
                else:
                    state['manifest'] = {
                        'status': 'REGISTRATION_CORRUPT',
                        'protocol_hash': None,
                        'eligible_volatility_horizons_h': [],
                        'blockers': ['PERSISTED_PREREGISTRATION_UNREADABLE'],
                    }
            return state['manifest']

        candidate = build_manifest(
            getattr(collector, 'EDGE_EVIDENCE_JOINT_COVERAGE_STATE', None)
        )
        state['manifest'] = candidate
        if candidate.get('status') == 'PREREGISTERED':
            if registration_file is not None:
                try:
                    _atomic_write_registration(registration_file, candidate)
                except Exception as exc:
                    state['persistence_error'] = f'{type(exc).__name__}: {exc}'
                    return state['manifest']
            state['registration_locked'] = True
            state['persistence_error'] = None
        return state['manifest']

    collector.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE = state
    collector.edge_evidence_interaction_protocol_refresh = refresh
    collector._EDGE_EVIDENCE_INTERACTION_PROTOCOL_INSTALLED = True

    if getattr(collector, 'production_decision', None) is not original_decision:
        raise RuntimeError('interaction protocol mutated production_decision')
    if getattr(collector, 'forward_observe', None) is not original_forward:
        raise RuntimeError('interaction protocol mutated forward_observe')
    return state
