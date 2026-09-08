from golden_thesis_engine import VERSION, build


def base():
    row = {"candidate_direction": "LONG", "data_degraded": False}
    out = {
        "decision": "LONG",
        "analysis_ready": True,
        "product_direction": "LONG",
        "entry_confirmation_direction": "LONG",
        "direction_alignment": "ALIGNED",
        "confidence": 72,
        "signal_threshold": 68,
        "risk_reward": 2.1,
        "geometry_readiness": {"ready": True},
        "setup_quality_gate": {"status": "PASS"},
        "evidence_profile": {"confirmations": ["STRUCTURAL_ROOM_CONFIRMED"], "warnings": []},
        "candidate_plan": {"direction": "LONG", "risk_reward": 2.1},
    }
    return row, out


def test_trade_ready_requires_complete_thesis():
    row, out = base()
    x = build(row, out)
    assert x["version"] == VERSION
    assert x["stage"] == "TRADE_READY"
    assert x["thesis_valid"] is True
    assert x["thesis_direction"] == "LONG"
    assert x["contradiction"] is None
    assert x["can_override_canonical_decision"] is False


def test_one_hour_cannot_flip_htf_thesis():
    row, out = base()
    out["decision"] = "WAIT"
    out["analysis_ready"] = False
    out["entry_confirmation_direction"] = "SHORT"
    out["direction_alignment"] = "OPPOSED"
    x = build(row, out)
    assert x["thesis_direction"] == "LONG"
    assert x["thesis_valid"] is False
    assert "ONE_HOUR_NOT_ALIGNED_WITH_HTF" in x["opposing_evidence"]


def test_geometry_failure_is_fatal():
    row, out = base()
    out["decision"] = "WAIT"
    out["analysis_ready"] = False
    out["geometry_readiness"] = {"ready": False}
    x = build(row, out)
    assert "CANONICAL_GEOMETRY_NOT_READY" in x["fatal_invalidations"]
    assert x["stage"] != "TRADE_READY"


def test_counterfactual_surfaces_strongest_failure():
    row, out = base()
    row["data_degraded"] = True
    out["data_degraded"] = True
    out["decision"] = "WAIT"
    out["analysis_ready"] = False
    x = build(row, out)
    assert "DATA_DEGRADED" in x["fatal_invalidations"]
    assert x["strongest_countercase"] in x["fatal_invalidations"]


def test_shadow_never_mutates_production_contract():
    row, out = base()
    x = build(row, out)
    assert x["can_change_score"] is False
    assert x["can_change_threshold"] is False
    assert x["can_change_geometry"] is False
    assert x["analysis_only"] is True
    assert x["live_execution"] is False
