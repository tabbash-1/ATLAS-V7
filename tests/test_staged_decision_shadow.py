from copy import deepcopy

from staged_decision_shadow import build_shadow


def canonical_row():
    return {
        "ok": True,
        "symbol": "BTCUSDT",
        "score": 75,
        "candidate_direction": "LONG",
        "product_direction": "LONG",
        "entry_confirmation_direction": "LONG",
        "direction_alignment": "ALIGNED",
        "entry": 100.0,
        "stop_loss": 98.0,
        "tp1": 102.0,
        "tp2": 104.0,
        "final_trade_gate": {
            "status": "TRADE_READY",
            "trade_ready": True,
            "product_direction": "LONG",
            "entry_confirmation_direction": "LONG",
            "direction_alignment": "ALIGNED",
        },
        "canonical_decision": {
            "decision": "LONG",
            "trade_ready": True,
            "source_of_truth": "FINAL_TRADE_GATE",
        },
    }


def test_shadow_never_mutates_canonical_decision_row():
    row = canonical_row()
    original = deepcopy(row)
    result = build_shadow(row)
    assert row == original
    assert result["canonical_decision"] == original["canonical_decision"]
    assert result["canonical_decision_unchanged"] is True
    assert result["final_trade_gate_unchanged"] is True
    assert result["can_override_production"] is False
    assert result["shadow_only"] is True


def test_missing_flow_and_cost_fail_closed_diagnostically_only():
    result = build_shadow(canonical_row())
    assert "flow_confirmation" in result["missing_evidence"]
    assert "cost_liquidity" in result["missing_evidence"]
    assert result["shadow_ready"] is False
    assert result["canonical_decision"]["decision"] == "LONG"


def test_explicit_cost_evidence_is_evaluated_without_changing_decision():
    row = canonical_row()
    row["expected_move_bps"] = 40
    row["execution_costs"] = {
        "fee_bps": 5,
        "spread_bps": 4,
        "slippage_bps": 6,
        "funding_bps": 1,
        "safety_multiplier": 1.25,
    }
    before = deepcopy(row["canonical_decision"])
    result = build_shadow(row)
    assert result["layers"]["cost_liquidity"]["passed"] is True
    assert result["layers"]["cost_liquidity"]["modeled_cost_bps"] == 16
    assert result["canonical_decision"] == before


def test_hype_is_not_a_canonical_shadow_asset():
    result = build_shadow({"symbol": "HYPEUSDT"})
    assert result["ok"] is False
    assert "HYPEUSDT" not in result["supported_symbols"]


def test_threshold_and_product_horizon_are_frozen():
    result = build_shadow(canonical_row())
    assert result["production_threshold"] == 68
    assert result["product_horizon"] == "4-12H"
    assert result["evaluation_horizons_h"] == [4, 8, 12]
