from htf_sr_decision_v2 import VERSION, apply, assess, build_sr_ladder


def _frame(bias, price=100.0, impulse="NEUTRAL", confidence="STRONG", atr=1.0):
    return {
        "ok": True,
        "bias": bias,
        "price": price,
        "impulse": impulse,
        "confidence": confidence,
        "atr14": atr,
        "volume_state": "NORMAL",
        "last_swing_low": price - 3.0,
        "last_swing_high": price + 3.0,
        "ema20": price - 1.0,
        "ema50": price - 2.0,
    }


def _row(**extra):
    row = {
        "ok": True,
        "symbol": "BTCUSDT",
        "candidate_direction": "LONG",
        "entry_confirmation_direction": "LONG",
        "product_direction": None,
        "direction_alignment": "NO_PRODUCT_DIRECTION",
        "pre_htf_actionable_decision": "LONG",
        "actionable_decision": "WAIT",
        "actionable_reason": "HTF_4H_12H_NOT_ALIGNED",
        "production_signal_qualified": True,
        "data_degraded": False,
        "can_execute": False,
        "htf_core_geometry": {"ready": True, "reason": "HTF_DIRECTION_AND_GEOMETRY_ALIGNED"},
        "htf_thesis": {
            "status": "WAIT",
            "direction": None,
            "product_direction": None,
            "direction_alignment": "NO_PRODUCT_DIRECTION",
            "reason": "4H_12H_NOT_ALIGNED",
            "frames": {
                "1h": _frame("LONG", 100.0, "BULLISH"),
                "4h": _frame("LONG", 100.0, "BULLISH"),
                "12h": _frame("NEUTRAL", 100.0, "NEUTRAL", "CONFLICT"),
                "1d": _frame("NEUTRAL", 100.0, "NEUTRAL", "CONFLICT"),
            },
        },
    }
    row.update(extra)
    return row


def test_4h_directional_12h_neutral_can_restore_only_prequalified_action():
    r = apply(_row())
    assert r["actionable_decision"] == "LONG"
    assert r["product_direction"] == "LONG"
    assert r["direction_alignment"] == "ALIGNED"
    assert r["conditional_htf_alignment"] is True
    assert r["htf_alignment_class"] == "CONDITIONAL_ALIGNED_12H_NEUTRAL"
    assert r["htf_sr_decision_v2"]["eligible"] is True
    assert r["htf_sr_decision_v2"]["score_changed"] is False
    assert r["htf_sr_decision_v2"]["threshold_changed"] is False


def test_explicit_12h_opposition_remains_wait():
    d = _row()
    d["htf_thesis"]["frames"]["12h"] = _frame("SHORT", 100.0, "BEARISH")
    r = apply(d)
    assert r["actionable_decision"] == "WAIT"
    assert r["htf_sr_decision_v2"]["eligible"] is False
    assert "12H_NOT_NEUTRAL" in r["htf_sr_decision_v2"]["blockers"]


def test_below_threshold_never_gets_promoted():
    r = apply(_row(production_signal_qualified=False))
    assert r["actionable_decision"] == "WAIT"
    assert "PRODUCTION_SIGNAL_NOT_QUALIFIED" in r["htf_sr_decision_v2"]["blockers"]


def test_pre_htf_wait_never_gets_manufactured_into_trade():
    r = apply(_row(pre_htf_actionable_decision="WAIT"))
    assert r["actionable_decision"] == "WAIT"
    assert "PRE_HTF_DECISION_NOT_ACTIONABLE" in r["htf_sr_decision_v2"]["blockers"]


def test_invalid_geometry_remains_wait():
    r = apply(_row(htf_core_geometry={"ready": False, "reason": "NO_ROOM"}))
    assert r["actionable_decision"] == "WAIT"
    assert "CANONICAL_GEOMETRY_NOT_READY" in r["htf_sr_decision_v2"]["blockers"]


def test_one_hour_opposition_remains_wait():
    d = _row()
    d["htf_thesis"]["frames"]["1h"] = _frame("SHORT", 100.0, "BEARISH")
    r = apply(d)
    assert r["actionable_decision"] == "WAIT"
    assert "1H_STRUCTURE_OPPOSES_4H" in r["htf_sr_decision_v2"]["blockers"]


def test_strong_daily_opposition_remains_wait():
    d = _row()
    d["htf_thesis"]["frames"]["1d"] = _frame("SHORT", 100.0, "BEARISH", "STRONG")
    r = apply(d)
    assert r["actionable_decision"] == "WAIT"
    assert "1D_MACRO_STRONGLY_OPPOSES_4H" in r["htf_sr_decision_v2"]["blockers"]


def test_expanding_4h_counter_impulse_remains_wait():
    d = _row()
    d["htf_thesis"]["frames"]["4h"] = _frame("LONG", 100.0, "BEARISH")
    d["htf_thesis"]["frames"]["4h"]["volume_state"] = "EXPANDING"
    r = apply(d)
    assert r["actionable_decision"] == "WAIT"
    assert "4H_COUNTER_IMPULSE_WITH_VOLUME" in r["htf_sr_decision_v2"]["blockers"]


def test_support_resistance_ladder_has_ordered_nearest_levels_and_confluence():
    thesis = _row()["htf_thesis"]
    ladder = build_sr_ladder(thesis)
    assert ladder["status"] == "READY"
    assert ladder["supports"]
    assert ladder["resistances"]
    assert ladder["supports"][0]["label"] == "S1"
    assert ladder["resistances"][0]["label"] == "R1"
    assert ladder["supports"][0]["price"] < ladder["price"]
    assert ladder["resistances"][0]["price"] > ladder["price"]
    assert ladder["supports"][0]["confluence_count"] >= 1
    assert ladder["geometry_changed"] is False


def test_layer_never_changes_threshold_score_or_risk_fields():
    d = _row(score=68.0, threshold=68.0, risk_pct=1.0)
    r = apply(d)
    assert r["score"] == 68.0
    assert r["threshold"] == 68.0
    assert r["risk_pct"] == 1.0
    assert r["htf_sr_decision_v2"]["score_changed"] is False
    assert r["htf_sr_decision_v2"]["threshold_changed"] is False
    assert r["htf_sr_decision_v2"]["geometry_changed"] is False


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"{VERSION} tests: {len(tests)} passed")
