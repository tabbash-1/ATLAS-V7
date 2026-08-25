from pathlib import Path
from types import SimpleNamespace

import edge_evidence_overlap as eeo
import edge_evidence_report as eer


def profit(supported=False, canonical=40):
    return {
        'walk_forward_report': {
            'version': 'P',
            'status': 'VALIDATION_READ_AVAILABLE' if supported else 'COLLECTING',
            'improves_production_expectancy': supported,
            'frozen_observations': 45,
            'settled_joined': 40,
            'canonical_execution_rows': canonical,
            'delta_average_r': 0.2 if supported else None,
            'drawdown_improvement_r': 1.0 if supported else None,
            'blockers': [] if supported else ['INSUFFICIENT_SETTLED_FROZEN_OBSERVATIONS'],
        }
    }


def micro(supported=False, canonical=40):
    return {
        'walk_forward_report': {
            'version': 'M',
            'status': 'VALIDATION_READ_AVAILABLE' if supported else 'COLLECTING',
            'evidence_supports_future_gate': supported,
            'frozen_observations': 45,
            'settled_joined': 40,
            'canonical_execution_rows': canonical,
            'aligned_average_r_delta_vs_baseline': 0.3 if supported else None,
            'opposed_average_r_delta_vs_baseline': -0.2 if supported else None,
            'blockers': [] if supported else ['INSUFFICIENT_ALIGNED_SETTLED'],
        }
    }


def vol(supported=False, canonical=40):
    return {
        'report': {
            'version': 'V',
            'status': 'VALIDATION_READ_AVAILABLE' if supported else 'COLLECTING',
            'horizons_supporting_future_filter': [4] if supported else [],
            'chosen_trade_horizon_assumed': False,
            'frozen_observations': 45,
            'settled_joined': 40,
            'canonical_execution_rows': canonical,
            'blockers': [] if supported else ['INSUFFICIENT_SETTLED_FROZEN_OBSERVATIONS'],
        }
    }


def overlap(*, comparable=True, union=40):
    if comparable:
        report = {
            'version': 'O',
            'status': 'COHORTS_IDENTICAL',
            'union_unique_forward_ids': union,
            'three_way_intersection_unique_forward_ids': union,
            'three_way_overlap_pct_of_union': 100.0,
            'missing_forward_id_counts_by_layer': {
                'profit_engine': 0,
                'microstructure': 0,
                'volatility': 0,
            },
            'duplicate_layers': [],
            'missing_files': [],
            'blockers': [],
        }
    else:
        report = {
            'version': 'O',
            'status': 'COHORT_MISMATCH',
            'union_unique_forward_ids': union,
            'three_way_intersection_unique_forward_ids': max(0, union - 2),
            'three_way_overlap_pct_of_union': 95.0 if union else None,
            'missing_forward_id_counts_by_layer': {
                'profit_engine': 0,
                'microstructure': 1,
                'volatility': 1,
            },
            'duplicate_layers': [],
            'missing_files': [],
            'blockers': ['FROZEN_SIGNAL_COHORTS_NOT_IDENTICAL'],
        }
    return {'report': report}


def redundancy(status='DESCRIPTIVE_READ_AVAILABLE', high=None):
    return {
        'report': {
            'version': 'R',
            'status': status,
            'matched_forward_ids': 40,
            'minimum_matched_observations': 20,
            'high_observed_association_pairs': list(high or []),
            'associations': {
                'profit_vs_microstructure': {
                    'cramers_v': 0.8 if high else 0.1,
                    'observed_association_strength': 'HIGH_OBSERVED_ASSOCIATION' if high else 'LOW_OBSERVED_ASSOCIATION',
                }
            },
            'shared_production_fields_excluded': ['direction', 'entry', 'score', 'signal_threshold'],
            'chosen_trade_horizon_assumed': False,
            'blockers': [] if status == 'DESCRIPTIVE_READ_AVAILABLE' else ['INSUFFICIENT_MATCHED_FROZEN_OBSERVATIONS'],
        }
    }


def test_all_collecting_stays_collecting_and_never_claims_live_readiness():
    out = eer.aggregate(profit(), micro(), vol(), overlap(), redundancy())
    assert out['status'] == 'COLLECTING'
    assert out['supported_layer_count'] == 0
    assert out['frozen_signal_cohorts_comparable'] is True
    assert out['redundancy_diagnostic_affects_status'] is False
    assert out['gate_promoted'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False
    assert out['weights_assigned'] is False
    assert out['composite_trade_score_created'] is False
    assert out['cross_layer_interaction_filtering_enabled'] is False


def test_one_validated_layer_is_partial_only():
    out = eer.aggregate(profit(True), micro(False), vol(False), overlap(), redundancy())
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layers'] == ['profit_engine']
    assert out['supported_layer_count'] == 1
    assert out['can_override_production'] is False


def test_all_three_supported_plus_identical_cohort_can_report_multilayer_evidence_but_not_gate():
    out = eer.aggregate(profit(True), micro(True), vol(True), overlap(comparable=True), redundancy())
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['supported_layer_count'] == 3
    assert out['canonical_execution_count_consistent'] is True
    assert out['frozen_signal_cohorts_comparable'] is True
    assert out['cohort_overlap']['status'] == 'COHORTS_IDENTICAL'
    assert out['layer_redundancy']['descriptive_read_available'] is True
    assert out['layer_redundancy']['informational_only'] is True
    assert out['layer_redundancy']['affects_multilayer_status'] is False
    assert out['layers']['volatility']['supported_horizons_h'] == [4]
    assert out['layers']['volatility']['chosen_trade_horizon_assumed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False


def test_high_observed_redundancy_does_not_demote_or_promote_multilayer_status():
    out = eer.aggregate(
        profit(True), micro(True), vol(True), overlap(),
        redundancy(high=['profit_vs_microstructure']),
    )
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['layer_redundancy']['high_observed_association_pairs'] == ['profit_vs_microstructure']
    assert out['layer_redundancy']['affects_multilayer_status'] is False
    assert out['redundancy_diagnostic_affects_status'] is False
    assert out['gate_promoted'] is False


def test_missing_redundancy_audit_is_informationally_unavailable_only():
    out = eer.aggregate(profit(True), micro(True), vol(True), overlap(), None)
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['layer_redundancy']['available'] is False
    assert out['layer_redundancy']['affects_multilayer_status'] is False


def test_all_three_supported_without_overlap_audit_is_partial_only():
    out = eer.aggregate(profit(True), micro(True), vol(True), None, redundancy())
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layer_count'] == 3
    assert out['frozen_signal_cohorts_comparable'] is False
    assert out['cohort_overlap']['available'] is False
    assert any('EDGE_EVIDENCE_OVERLAP_AUDIT_UNAVAILABLE' in x for x in out['blockers'])


def test_all_three_supported_with_cohort_mismatch_is_partial_only():
    out = eer.aggregate(profit(True), micro(True), vol(True), overlap(comparable=False), redundancy())
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layer_count'] == 3
    assert out['canonical_execution_count_consistent'] is True
    assert out['frozen_signal_cohorts_comparable'] is False
    assert out['cohort_overlap']['status'] == 'COHORT_MISMATCH'
    assert any('FROZEN_SIGNAL_COHORTS_NOT_IDENTICAL' in x for x in out['blockers'])


def test_canonical_count_mismatch_prevents_multilayer_status_even_with_identical_cohort():
    out = eer.aggregate(profit(True, 40), micro(True, 41), vol(True, 40), overlap(), redundancy())
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layer_count'] == 3
    assert out['canonical_execution_count_consistent'] is False
    assert out['frozen_signal_cohorts_comparable'] is True
    assert 'CANONICAL_EXECUTION_COUNT_MISMATCH_ACROSS_LAYER_REPORTS' in out['blockers']


def test_missing_runtime_is_explicit_unavailable_blocker():
    out = eer.aggregate(profit(True), None, vol(True), overlap(), redundancy())
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['layers']['microstructure']['available'] is False
    assert 'microstructure' in out['unavailable_layers']
    assert any('MICROSTRUCTURE_RUNTIME_UNAVAILABLE' in x for x in out['blockers'])


def test_install_is_read_only_and_refresh_reads_current_states(tmp_path):
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=decision,
        forward_observe=forward,
        PROFIT_ENGINE_RUNTIME_STATE=profit(False),
        MICROSTRUCTURE_RUNTIME_STATE=micro(False),
        VOLATILITY_WALKFORWARD_RUNTIME_STATE=vol(False),
    )
    state = eer.install(collector)
    assert collector.production_decision is decision
    assert collector.forward_observe is forward
    assert state['read_only'] is True
    assert state['wraps_production_decision'] is False
    assert state['wraps_forward_observe'] is False
    assert state['report']['status'] == 'COLLECTING'
    assert hasattr(collector, 'EDGE_EVIDENCE_OVERLAP_STATE')
    assert hasattr(collector, 'EDGE_EVIDENCE_REDUNDANCY_STATE')

    collector.PROFIT_ENGINE_RUNTIME_STATE = profit(True)
    refreshed = collector.edge_evidence_refresh()
    assert refreshed['status'] == 'PARTIAL_EVIDENCE'
    assert refreshed['layer_redundancy']['informational_only'] is True
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_can_become_multilayer_only_after_identical_sidecars_exist(tmp_path):
    import json

    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=decision,
        forward_observe=forward,
        PROFIT_ENGINE_RUNTIME_STATE=profit(True, 1),
        MICROSTRUCTURE_RUNTIME_STATE=micro(True, 1),
        VOLATILITY_WALKFORWARD_RUNTIME_STATE=vol(True, 1),
    )
    state = eer.install(collector)
    assert state['report']['status'] == 'PARTIAL_EVIDENCE'

    for layer in ('profit_engine', 'microstructure', 'volatility'):
        path = Path(tmp_path) / eeo.FILES[layer]
        path.write_text(json.dumps({
            'schema': eeo.SCHEMAS[layer],
            'forward_id': 'F1',
            'production_signal_qualified': True,
            'research_sample': False,
        }) + '\n', encoding='utf-8')

    refreshed = collector.edge_evidence_refresh()
    assert refreshed['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert refreshed['frozen_signal_cohorts_comparable'] is True
    # One sample is insufficient for redundancy inference, but that diagnostic is
    # intentionally not a gate on independent layer evidence status.
    assert refreshed['layer_redundancy']['status'] == 'COLLECTING'
    assert refreshed['redundancy_diagnostic_affects_status'] is False
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_is_idempotent(tmp_path):
    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=lambda symbol: {'ok': True},
        forward_observe=lambda payload: {'id': 'F1'},
        PROFIT_ENGINE_RUNTIME_STATE=profit(),
        MICROSTRUCTURE_RUNTIME_STATE=micro(),
        VOLATILITY_WALKFORWARD_RUNTIME_STATE=vol(),
    )
    first = eer.install(collector)
    second = eer.install(collector)
    assert first is second
