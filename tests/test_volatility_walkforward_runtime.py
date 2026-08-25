from pathlib import Path
from types import SimpleNamespace

import volatility_walkforward_runtime as vwr


class FakeThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return None


def collector(tmp_path):
    calls = {'decision': 0, 'forward': 0}

    def decision(symbol):
        calls['decision'] += 1
        return {'ok': True, 'symbol': symbol, 'actionable_decision': 'LONG'}

    def forward(payload):
        calls['forward'] += 1
        return {'id': 'F1'}

    c = SimpleNamespace(
        DATA=Path(tmp_path),
        production_decision=decision,
        forward_observe=forward,
        read_forward=lambda: [],
        now_iso=lambda: '2026-08-25T18:00:00+00:00',
    )
    c._calls = calls
    return c


def test_install_does_not_wrap_decision_or_forward(monkeypatch, tmp_path):
    c = collector(tmp_path)
    original_decision = c.production_decision
    original_forward = c.forward_observe
    monkeypatch.setattr(vwr.threading, 'Thread', FakeThread)
    state = vwr.install(c)

    assert c.production_decision is original_decision
    assert c.forward_observe is original_forward
    assert state['background_only'] is True
    assert state['wraps_production_decision'] is False
    assert state['wraps_forward_observe'] is False
    assert state['can_override_production'] is False
    assert hasattr(c, 'EDGE_EVIDENCE_REPORT_STATE')
    assert hasattr(c, 'EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE')
    assert hasattr(c, 'EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE')

    manifest = c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE['manifest']
    assert manifest['outcomes_read'] is False
    assert manifest['interaction_outcome_testing_performed'] is False
    assert manifest['interaction_filter_activation_allowed'] is False
    assert manifest['gate_promoted'] is False
    assert manifest['can_override_production'] is False

    guard = c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE['report']
    assert guard['outcomes_read'] is False
    assert guard['validator_execution_started'] is False
    assert guard['interaction_outcome_testing_performed'] is False
    assert guard['rule_selection_allowed'] is False
    assert guard['grid_search_allowed'] is False
    assert guard['interaction_filter_activation_allowed'] is False
    assert guard['gate_promoted'] is False
    assert guard['can_override_production'] is False


def test_successful_refresh_updates_governance_in_edge_protocol_guard_order(monkeypatch, tmp_path):
    c = collector(tmp_path)
    original_decision = c.production_decision
    original_forward = c.forward_observe
    monkeypatch.setattr(vwr.threading, 'Thread', FakeThread)
    state = vwr.install(c)
    expected = {
        'version': 'TEST',
        'status': 'COLLECTING',
        'horizons_supporting_future_filter': [],
        'gate_promoted': False,
        'can_override_production': False,
    }
    monkeypatch.setattr(vwr, 'build_report', lambda *args, **kwargs: dict(expected))
    old_hash = c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE['manifest']['protocol_hash']
    out = c.volatility_refresh_walkforward()
    assert out == expected
    assert state['report'] == expected
    assert state['refreshes'] == 1
    assert c._calls == {'decision': 0, 'forward': 0}
    assert c.production_decision is original_decision
    assert c.forward_observe is original_forward

    new_manifest = c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE['manifest']
    assert new_manifest['protocol_hash']
    assert new_manifest['outcomes_read'] is False
    assert isinstance(old_hash, str) and isinstance(new_manifest['protocol_hash'], str)

    guard = c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE['report']
    assert guard['protocol_hash_required'] is True
    assert guard['outcomes_read'] is False
    assert guard['validator_execution_started'] is False
    assert guard['cross_layer_interaction_filtering_enabled'] is False


def test_refresh_failure_is_unavailable_and_cannot_touch_production(monkeypatch, tmp_path):
    c = collector(tmp_path)
    original_decision = c.production_decision
    original_forward = c.forward_observe
    monkeypatch.setattr(vwr.threading, 'Thread', FakeThread)
    state = vwr.install(c)
    monkeypatch.setattr(
        vwr,
        'build_report',
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    assert c.volatility_refresh_walkforward() is None
    assert state['report']['status'] == 'UNAVAILABLE'
    assert state['report']['gate_promoted'] is False
    assert state['report']['can_override_production'] is False
    assert c.production_decision is original_decision
    assert c.forward_observe is original_forward

    manifest = c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE['manifest']
    assert manifest['interaction_outcome_testing_performed'] is False
    assert manifest['cross_layer_interaction_filtering_enabled'] is False

    guard = c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE['report']
    assert guard['validator_execution_started'] is False
    assert guard['interaction_outcome_testing_performed'] is False
    assert guard['cross_layer_interaction_filtering_enabled'] is False
    assert guard['interaction_filter_activation_allowed'] is False

    assert c.production_decision('BTCUSDT')['actionable_decision'] == 'LONG'
    assert c._calls['decision'] == 1


def test_idempotent_install(monkeypatch, tmp_path):
    c = collector(tmp_path)
    monkeypatch.setattr(vwr.threading, 'Thread', FakeThread)
    first = vwr.install(c)
    protocol_first = c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE
    guard_first = c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE
    second = vwr.install(c)
    assert second is first
    assert c.EDGE_EVIDENCE_INTERACTION_PROTOCOL_STATE is protocol_first
    assert c.EDGE_EVIDENCE_INTERACTION_VALIDATOR_GUARD_STATE is guard_first
