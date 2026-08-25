from pathlib import Path
from types import SimpleNamespace

import edge_evidence_report as eer


def _profit():
    return {'walk_forward_report': {
        'status': 'VALIDATION_READ_AVAILABLE',
        'improves_production_expectancy': True,
        'canonical_execution_rows': 40,
        'blockers': [],
    }}


def _micro():
    return {'walk_forward_report': {
        'status': 'VALIDATION_READ_AVAILABLE',
        'evidence_supports_future_gate': True,
        'canonical_execution_rows': 40,
        'blockers': [],
    }}


def _vol():
    return {'report': {
        'status': 'VALIDATION_READ_AVAILABLE',
        'horizons_supporting_future_filter': [4],
        'canonical_execution_rows': 40,
        'blockers': [],
    }}


def _overlap():
    return {'report': {
        'status': 'COHORTS_IDENTICAL',
        'union_unique_forward_ids': 40,
        'three_way_intersection_unique_forward_ids': 40,
        'blockers': [],
    }}


def _joint(status='SPARSE_INTERACTION_DESIGN', supported=False):
    return {'report': {
        'status': status,
        'matched_forward_ids': 40,
        'minimum_matched_observations': 30,
        'minimum_cell_n': 10,
        'horizons_with_sufficient_joint_coverage_h': [4] if supported else [],
        'future_interaction_validation_supported': supported,
        'chosen_trade_horizon_assumed': False,
        'outcomes_read': False,
        'performance_metrics_computed': False,
        'rules_searched': False,
        'grid_search_performed': False,
        'interaction_rule_selection_allowed': False,
        'interaction_outcome_testing_performed': False,
        'blockers': [] if supported else ['H4:TOO_FEW_WELL_POPULATED_JOINT_CELLS'],
    }}


def test_sparse_joint_coverage_does_not_demote_existing_multilayer_evidence():
    out = eer.aggregate(_profit(), _micro(), _vol(), _overlap(), None, _joint())
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['joint_cell_coverage']['status'] == 'SPARSE_INTERACTION_DESIGN'
    assert out['joint_cell_coverage']['future_interaction_validation_supported'] is False
    assert out['joint_cell_coverage']['affects_multilayer_status'] is False
    assert out['joint_coverage_diagnostic_affects_status'] is False
    assert out['interaction_validation_started'] is False
    assert out['cross_layer_interaction_filtering_enabled'] is False
    assert out['gate_promoted'] is False


def test_sufficient_joint_coverage_only_allows_future_validation_design_not_rules_or_trading():
    out = eer.aggregate(
        _profit(), _micro(), _vol(), _overlap(), None,
        _joint('DESIGN_READ_AVAILABLE', True),
    )
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    joint = out['joint_cell_coverage']
    assert joint['future_interaction_validation_supported'] is True
    assert joint['horizons_with_sufficient_joint_coverage_h'] == [4]
    assert joint['interaction_rule_selection_allowed'] is False
    assert joint['interaction_outcome_testing_performed'] is False
    assert joint['outcomes_read'] is False
    assert joint['performance_metrics_computed'] is False
    assert joint['rules_searched'] is False
    assert joint['grid_search_performed'] is False
    assert out['interaction_validation_started'] is False
    assert out['can_override_production'] is False


def test_missing_joint_audit_is_informationally_unavailable_only():
    out = eer.aggregate(_profit(), _micro(), _vol(), _overlap(), None, None)
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['joint_cell_coverage']['available'] is False
    assert out['joint_cell_coverage']['affects_multilayer_status'] is False
    assert out['joint_cell_coverage']['future_interaction_validation_supported'] is False


def test_install_adds_joint_audit_without_wrapping_production(tmp_path):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=decision,
        forward_observe=forward,
        PROFIT_ENGINE_RUNTIME_STATE=_profit(),
        MICROSTRUCTURE_RUNTIME_STATE=_micro(),
        VOLATILITY_WALKFORWARD_RUNTIME_STATE=_vol(),
    )
    state = eer.install(collector)
    assert hasattr(collector, 'EDGE_EVIDENCE_JOINT_COVERAGE_STATE')
    assert hasattr(collector, 'edge_evidence_joint_coverage_refresh')
    assert state['wraps_production_decision'] is False
    assert state['wraps_forward_observe'] is False
    assert collector.production_decision is decision
    assert collector.forward_observe is forward
