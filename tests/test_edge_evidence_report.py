from types import SimpleNamespace

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


def test_all_collecting_stays_collecting_and_never_claims_live_readiness():
    out = eer.aggregate(profit(), micro(), vol())
    assert out['status'] == 'COLLECTING'
    assert out['supported_layer_count'] == 0
    assert out['gate_promoted'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False
    assert out['weights_assigned'] is False
    assert out['composite_trade_score_created'] is False
    assert out['cross_layer_interaction_filtering_enabled'] is False


def test_one_validated_layer_is_partial_only():
    out = eer.aggregate(profit(True), micro(False), vol(False))
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layers'] == ['profit_engine']
    assert out['supported_layer_count'] == 1
    assert out['can_override_production'] is False


def test_all_three_independently_supported_can_report_multilayer_evidence_but_not_gate():
    out = eer.aggregate(profit(True), micro(True), vol(True))
    assert out['status'] == 'MULTI_LAYER_EVIDENCE_AVAILABLE'
    assert out['supported_layer_count'] == 3
    assert out['canonical_execution_count_consistent'] is True
    assert out['layers']['volatility']['supported_horizons_h'] == [4]
    assert out['layers']['volatility']['chosen_trade_horizon_assumed'] is False
    assert out['gate_promoted'] is False
    assert out['can_override_production'] is False
    assert out['production_ready_claimed'] is False
    assert out['live_trading_ready_claimed'] is False


def test_canonical_count_mismatch_prevents_multilayer_status():
    out = eer.aggregate(profit(True, 40), micro(True, 41), vol(True, 40))
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['supported_layer_count'] == 3
    assert out['canonical_execution_count_consistent'] is False
    assert 'CANONICAL_EXECUTION_COUNT_MISMATCH_ACROSS_LAYER_REPORTS' in out['blockers']


def test_missing_runtime_is_explicit_unavailable_blocker():
    out = eer.aggregate(profit(True), None, vol(True))
    assert out['status'] == 'PARTIAL_EVIDENCE'
    assert out['layers']['microstructure']['available'] is False
    assert 'microstructure' in out['unavailable_layers']
    assert any('MICROSTRUCTURE_RUNTIME_UNAVAILABLE' in x for x in out['blockers'])


def test_install_is_read_only_and_refresh_reads_current_states():
    decision = lambda symbol: {'ok': True, 'symbol': symbol}
    forward = lambda payload: {'id': 'F1'}
    collector = SimpleNamespace(
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

    collector.PROFIT_ENGINE_RUNTIME_STATE = profit(True)
    refreshed = collector.edge_evidence_refresh()
    assert refreshed['status'] == 'PARTIAL_EVIDENCE'
    assert collector.production_decision is decision
    assert collector.forward_observe is forward


def test_install_is_idempotent():
    collector = SimpleNamespace(
        production_decision=lambda symbol: {'ok': True},
        forward_observe=lambda payload: {'id': 'F1'},
        PROFIT_ENGINE_RUNTIME_STATE=profit(),
        MICROSTRUCTURE_RUNTIME_STATE=micro(),
        VOLATILITY_WALKFORWARD_RUNTIME_STATE=vol(),
    )
    first = eer.install(collector)
    second = eer.install(collector)
    assert first is second
