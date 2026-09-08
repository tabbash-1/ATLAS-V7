from final_trade_ready_guard import apply


def _row():
    return {
        "ok": True,
        "symbol": "BTCUSDT",
        "score": 72.0,
        "signal_threshold": 68.0,
        "candidate_direction": "LONG",
        "product_direction": "LONG",
        "entry_confirmation_direction": "LONG",
        "direction_alignment": "ALIGNED",
        "actionable_decision": "LONG",
        "production_signal_qualified": True,
        "htf_core_geometry": {"ready": True, "reason": "HTF_GEOMETRY_READY"},
        "setup_quality_gate": {"status": "PASS"},
        "trade_plan": {"entry": 100.0, "stop_loss": 95.0, "tp1": 110.0, "tp2": 115.0, "rr_tp2": 3.0},
        "analyst_output": {
            "decision": "LONG",
            "analysis_ready": True,
            "product_direction": "LONG",
            "entry_confirmation_direction": "LONG",
            "direction_alignment": "ALIGNED",
            "confidence": 72.0,
            "signal_threshold": 68.0,
            "risk_reward": 3.0,
            "geometry_readiness": {"ready": True},
            "setup_quality_gate": {"status": "PASS"},
            "evidence_profile": {"confirmations": ["STRUCTURAL_ROOM_CONFIRMED"], "warnings": []},
            "candidate_plan": {"direction": "LONG", "risk_reward": 3.0},
        },
    }


def test_final_gate_binds_golden_to_canonical_decision_id():
    out = apply(_row())
    assert out["final_trade_gate"]["status"] == "TRADE_READY"
    assert out["canonical_decision"]["decision"] == "LONG"
    assert out["golden_thesis"]["bound_after_final_trade_gate"] is True
    assert out["golden_thesis"]["canonical_decision_id"] == out["canonical_decision_id"]
    assert out["analyst_output"]["golden_thesis"]["canonical_decision"] == "LONG"
    assert out["golden_thesis"]["can_override_canonical_decision"] is False


def test_final_gate_wait_is_reflected_in_golden_thesis():
    row = _row()
    row["entry_confirmation_direction"] = "SHORT"
    row["direction_alignment"] = "OPPOSED"
    row["analyst_output"]["entry_confirmation_direction"] = "SHORT"
    row["analyst_output"]["direction_alignment"] = "OPPOSED"
    out = apply(row)
    assert out["canonical_decision"]["decision"] == "WAIT"
    assert out["analyst_output"]["decision"] == "WAIT"
    assert out["golden_thesis"]["canonical_decision"] == "WAIT"
    assert out["golden_thesis"]["stage"] != "TRADE_READY"
