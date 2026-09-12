from copy import deepcopy

from evolution_scorecard import BASELINE, build_scorecard, validate_canonical_trades


def _portfolio():
    trades = [
        {
            "decision_id": "a",
            "decision_action": "TRADE_READY",
            "decision_source": "FINAL_TRADE_GATE",
            "paper_only": True,
            "live_execution": False,
            "product_horizon": "4-12H",
            "direction": "LONG",
            "settlement": {"terminal": True, "status": "LOSS", "r_multiple": -1.0},
        },
        {
            "decision_id": "b",
            "decision_action": "TRADE_READY",
            "decision_source": "FINAL_TRADE_GATE",
            "paper_only": True,
            "live_execution": False,
            "product_horizon": "4-12H",
            "direction": "SHORT",
            "settlement": {"terminal": True, "status": "TP2", "r_multiple": 2.0},
        },
        {
            "decision_id": "c",
            "decision_action": "TRADE_READY",
            "decision_source": "FINAL_TRADE_GATE",
            "paper_only": True,
            "live_execution": False,
            "product_horizon": "4-12H",
            "direction": "SHORT",
            "settlement": {"terminal": True, "status": "EXPIRED", "r_multiple": 0.5592},
        },
    ]
    return {
        "schema": "ATLAS_PAPER_PORTFOLIO_10K_V3_CANONICAL_TRUTH",
        "decision_source_of_truth": "FINAL_TRADE_GATE",
        "paper_only": True,
        "live_execution": False,
        "production_threshold_unchanged": 68,
        "cost_note": "gross paper only",
        "trades": trades,
        "portfolio": {
            "entries": 3,
            "closed": 3,
            "wins": 2,
            "losses": 1,
            "open_or_unresolved": 0,
            "win_rate_pct": 66.67,
            "net_r": 1.5592,
            "avg_r": 0.5197,
            "profit_factor": 2.5592,
            "max_drawdown_pct": 1.0,
            "return_pct": 1.53,
            "equity_usd": 10153.0,
            "starting_equity_usd": 10000.0,
        },
    }


def test_baseline_is_frozen_contract():
    assert BASELINE["entries"] == 3
    assert BASELINE["net_r"] == 1.5592
    assert BASELINE["profit_factor"] == 2.5336
    assert BASELINE["max_drawdown_pct"] == 1.0


def test_duplicate_decision_ids_rejected():
    p = _portfolio()
    p["trades"][1]["decision_id"] = "a"
    try:
        validate_canonical_trades(p["trades"])
    except AssertionError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate canonical decision_id was accepted")


def test_non_trade_ready_rejected():
    p = _portfolio()
    p["trades"][0]["decision_action"] = "WAIT"
    try:
        validate_canonical_trades(p["trades"])
    except AssertionError as exc:
        assert "TRADE_READY" in str(exc)
    else:
        raise AssertionError("WAIT entered canonical KPI")


def test_shadow_or_historical_cannot_override_kpi():
    report = build_scorecard(
        _portfolio(),
        {"forward_trade_ready_count": 999, "forward_wait_directional_count": 1234},
        {"analysis_only": True, "rows": [{"r_multiple": 100.0}]},
    )
    assert report["canonical_forward_performance"]["entries"] == 3
    assert report["evidence_lanes"]["historical_counterfactual"]["may_override_kpi"] is False
    assert report["evidence_lanes"]["shadow"]["may_override_kpi"] is False
    assert report["evidence_lanes"]["analyst_forward_attribution"]["may_override_kpi"] is False
    assert report["integrity"]["historical_or_shadow_in_official_kpi"] is False


def test_direction_cohorts_sum_to_canonical_entries():
    report = build_scorecard(_portfolio())
    assert report["direction_cohorts"]["LONG"]["entries"] == 1
    assert report["direction_cohorts"]["SHORT"]["entries"] == 2
    assert report["integrity"]["direction_entries_sum"] == 3


def test_small_sample_cannot_claim_improvement():
    report = build_scorecard(_portfolio())
    assert report["comparison_to_baseline"]["claim_allowed"] is False
    assert report["comparison_to_baseline"]["verdict"] == "EARLY / INSUFFICIENT SAMPLE"


def test_cost_label_is_preserved():
    p = _portfolio()
    p["cost_note"] = "fees funding slippage not deducted"
    report = build_scorecard(p)
    assert report["cost_basis"] == "GROSS_PAPER_BEFORE_FEES_FUNDING_SLIPPAGE"
    assert report["cost_note"] == "fees funding slippage not deducted"


def test_input_is_not_mutated():
    p = _portfolio()
    before = deepcopy(p)
    build_scorecard(p)
    assert p == before


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"EVOLUTION_SCORECARD_TESTS_OK {len(tests)}")
