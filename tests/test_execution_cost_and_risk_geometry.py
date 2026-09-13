import math
import pytest

from atlas_execution_cost import evaluate_execution_cost
from atlas_risk_geometry import evaluate_risk_geometry, size_position_from_stop


def test_cost_gate_passes_only_with_safety_margin():
    r = evaluate_execution_cost(expected_move_bps=40, fee_bps=5, spread_bps=4, slippage_bps=6, funding_bps=1, safety_multiplier=1.25)
    assert r.modeled_cost_bps == 16
    assert r.required_edge_bps == 20
    assert r.net_edge_bps == 24
    assert r.passed is True


def test_cost_gate_fails_when_expected_move_does_not_clear_buffer():
    r = evaluate_execution_cost(expected_move_bps=17, fee_bps=5, spread_bps=4, slippage_bps=4, funding_bps=1, safety_multiplier=1.25)
    assert r.modeled_cost_bps == 14
    assert r.required_edge_bps == 17.5
    assert r.passed is False
    assert r.reason == 'INSUFFICIENT_EDGE_AFTER_COST'


def test_cost_gate_rejects_negative_inputs():
    with pytest.raises(ValueError):
        evaluate_execution_cost(expected_move_bps=20, fee_bps=-1, spread_bps=1, slippage_bps=1)


def test_long_geometry_and_rr():
    r = evaluate_risk_geometry(direction='LONG', entry=100, stop=98, tp1=102, tp2=104)
    assert r.geometry_valid is True
    assert r.rr_tp1 == 1
    assert r.rr_tp2 == 2


def test_short_geometry_and_rr():
    r = evaluate_risk_geometry(direction='SHORT', entry=100, stop=102, tp1=98, tp2=96)
    assert r.geometry_valid is True
    assert r.rr_tp1 == 1
    assert r.rr_tp2 == 2


def test_invalid_geometry_fails_closed():
    r = evaluate_risk_geometry(direction='LONG', entry=100, stop=101, tp1=102, tp2=104)
    assert r.geometry_valid is False
    assert r.rr_tp2 == 0


def test_position_sizing_uses_stop_distance_and_reports_atr_context():
    r = size_position_from_stop(account_equity=10_000, risk_pct=1, entry=100, stop=98, atr=1)
    assert r.risk_budget == 100
    assert r.units == 50
    assert r.notional == 5000
    assert math.isclose(r.stop_distance_atr, 2.0)
