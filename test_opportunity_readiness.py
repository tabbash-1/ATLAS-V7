import types

from opportunity_readiness import assess, install


def decision(symbol, score, qualified, product_direction, alignment, blockers, trade_ready=False, htf_reason=None):
    return {
        "ok": True,
        "symbol": symbol,
        "actionable_decision": "SHORT" if trade_ready else "WAIT",
        "candidate_direction": "SHORT",
        "product_direction": product_direction,
        "direction_alignment": alignment,
        "score": score,
        "signal_threshold": 68.0,
        "production_signal_qualified": qualified,
        "final_trade_gate": {"trade_ready": trade_ready, "blockers": blockers},
        "htf_thesis": {"status": "PASS" if product_direction else "WAIT", "reason": htf_reason},
    }


def test_trade_ready_is_always_ranked_first_and_scored_100():
    rows = {
        "BTCUSDT": decision("BTCUSDT", 90, True, None, "NO_PRODUCT_DIRECTION", ["HTF_PRODUCT_DIRECTION_UNRESOLVED"], False, "4H_12H_NOT_ALIGNED"),
        "XRPUSDT": decision("XRPUSDT", 70, True, "SHORT", "ALIGNED", [], True, "HTF_ALIGNED_CURRENT_PHASE_ACCEPTABLE"),
    }
    atlas = types.SimpleNamespace(
        ON_DEMAND_SYMBOLS=tuple(rows),
        production_decision=lambda symbol: rows[symbol],
    )
    install(atlas)
    ranked = atlas.opportunity_readiness()
    assert ranked["opportunities"][0]["symbol"] == "XRPUSDT"
    assert ranked["opportunities"][0]["readiness_score"] == 100
    assert ranked["production_decision_changed"] is False
    assert ranked["readiness_score_is_probability"] is False


def test_htf_aligned_but_below_threshold_is_closer_than_unresolved_htf():
    xrp = decision(
        "XRPUSDT", 65, False, "SHORT", "ALIGNED",
        ["PRE_FINAL_DECISION_NOT_ACTIONABLE", "PRODUCTION_SIGNAL_NOT_QUALIFIED", "BREAKOUT_STRUCTURE_NOT_CONFIRMED"],
        False, "HTF_ALIGNED_CURRENT_PHASE_ACCEPTABLE",
    )
    zec = decision(
        "ZECUSDT", 74, True, None, "NO_PRODUCT_DIRECTION",
        ["HTF_PRODUCT_DIRECTION_UNRESOLVED", "HTF_4H_12H_NOT_ALIGNED", "PRE_FINAL_DECISION_NOT_ACTIONABLE"],
        False, "4H_12H_NOT_ALIGNED",
    )
    ax = assess(xrp)
    az = assess(zec)
    assert ax["readiness_score"] > az["readiness_score"]
    assert ax["score_gap_to_threshold"] == 3.0
    assert az["score_gap_to_threshold"] == 0.0
    assert "production_score_qualified" in ax["missing_conditions"]
    assert "htf_direction_resolved" in az["missing_conditions"]


def test_ranking_never_changes_threshold_or_score():
    row = decision("BTCUSDT", 69, True, None, "NO_PRODUCT_DIRECTION", ["HTF_PRODUCT_DIRECTION_UNRESOLVED", "HTF_4H_12H_NOT_ALIGNED"], False, "4H_12H_NOT_ALIGNED")
    atlas = types.SimpleNamespace(ON_DEMAND_SYMBOLS=("BTCUSDT",), production_decision=lambda symbol: dict(row))
    install(atlas)
    ranked = atlas.opportunity_readiness()
    item = ranked["opportunities"][0]
    assert item["score"] == 69
    assert item["signal_threshold"] == 68.0
    assert ranked["threshold_changed"] is False
    assert ranked["score_changed"] is False
