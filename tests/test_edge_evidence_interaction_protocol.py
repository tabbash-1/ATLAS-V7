from types import SimpleNamespace

import edge_evidence_interaction_protocol as eip


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


def test_ready_design_preregisters_all_eligible_horizons_without_selecting_one():
    out = eip.build_manifest(joint())
    assert out['status'] == 'PREREGISTERED'
    assert out['eligible_volatility_horizons_h'] == [1, 4, 12]
    assert out['all_eligible_horizons_must_be_reported_separately'] is True
    assert out['single_horizon_selection_allowed'] is False
    assert out['chosen_trade_horizon_assumed'] is False
    assert out['split_policy']['type'] == 'CHRONOLOGICAL_NON_SHUFFLED_FOLDS'
    assert out['split_policy']['fold_count'] == 3
    assert out['multiple_testing_policy']['grid_search_allowed'] is False
    assert out['multiple_testing_policy']['adaptive_rule_search_allowed'] is False
    assert out['multiple_testing_policy']['threshold_tuning_after_outcomes_allowed'] is False
    assert out['multiple_testing_policy']['best_cell_selection_after_outcomes_allowed'] is False
    assert out['outcomes_read'] is False
    assert out['interaction_outcome_testing_performed'] is False
    assert out['interaction_filter_activation_allowed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert eip.verify_manifest(out) is True


def test_sparse_design_is_blocked_and_still_hashes_deterministically():
    a = eip.build_manifest(joint('SPARSE_INTERACTION_DESIGN', False, []))
    b = eip.build_manifest(joint('SPARSE_INTERACTION_DESIGN', False, []))
    assert a['status'] == 'BLOCKED_BY_DESIGN'
    assert a['eligible_volatility_horizons_h'] == []
    assert a['protocol_hash'] == b['protocol_hash']
    assert eip.verify_manifest(a) is True
    assert 'JOINT_COVERAGE_DESIGN_NOT_READY' in a['blockers']


def test_hash_changes_if_protocol_is_tampered_after_registration():
    out = eip.build_manifest(joint())
    original = out['protocol_hash']
    out['minimum_samples']['total_settled'] += 1
    assert out['protocol_hash'] == original
    assert eip.verify_manifest(out) is False


def test_hash_changes_across_distinct_eligible_horizon_sets():
    a = eip.build_manifest(joint(horizons=[1, 4]))
    b = eip.build_manifest(joint(horizons=[4, 12]))
    assert a['protocol_hash'] != b['protocol_hash']
    assert a['single_horizon_selection_allowed'] is False
    assert b['single_horizon_selection_allowed'] is False


def test_shared_production_fields_are_forbidden_predictors():
    out = eip.build_manifest(joint())
    assert set(out['shared_production_fields_forbidden_as_interaction_predictors']) == {
        'direction', 'entry', 'score', 'signal_threshold'
    }
    assert out['allowed_predictor_variables']['profit_engine'] == ['PROFIT_REGIME_RELATION']
    assert out['allowed_predictor_variables']['microstructure'] == ['MICROSTRUCTURE_RELATION_TO_SIGNAL']
    assert out['allowed_predictor_variables']['volatility_per_horizon'] == [
        'VOLATILITY_TARGET_FIT', 'VOLATILITY_STOP_FIT'
    ]


def test_install_is_read_only_refreshable_and_idempotent():
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(
        production_decision=decision,
        forward_observe=forward,
        EDGE_EVIDENCE_JOINT_COVERAGE_STATE=joint('COLLECTING', False, []),
    )
    first = eip.install(collector)
    assert first['manifest']['status'] == 'BLOCKED_BY_DESIGN'
    assert first['read_only'] is True
    assert first['wraps_production_decision'] is False
    assert first['wraps_forward_observe'] is False
    assert collector.production_decision is decision
    assert collector.forward_observe is forward

    collector.EDGE_EVIDENCE_JOINT_COVERAGE_STATE = joint()
    refreshed = collector.edge_evidence_interaction_protocol_refresh()
    assert refreshed['status'] == 'PREREGISTERED'
    assert eip.verify_manifest(refreshed) is True
    assert collector.production_decision is decision
    assert collector.forward_observe is forward

    second = eip.install(collector)
    assert first is second
