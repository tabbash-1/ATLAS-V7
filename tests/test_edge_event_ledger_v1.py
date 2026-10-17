from pathlib import Path
import copy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.edge_event_ledger_v1 import (
    HOUR_MS, SCHEMA, build_ledger, frozen_features, normalize_candles, settle_path,
)


def candle(i, close=100.0, start=0, high=None, low=None, open_price=None):
    p = close
    return {
        "time": start + i * HOUR_MS,
        "close_time": start + (i + 1) * HOUR_MS - 1,
        "open": p if open_price is None else open_price,
        "high": p + .4 if high is None else high,
        "low": p - .4 if low is None else low,
        "close": p,
        "volume": 100 + i,
    }


def history(n=64):
    return [candle(i, close=100 + .05 * i) for i in range(n)]


def future_path(first, more=None):
    more = more or []
    return [first] + more + [candle(k + 1) for k in range(11 - len(more))]


def test_first_touch_tp_and_sl():
    tp = future_path(candle(0, close=100, high=101.5, low=99.8))
    sl = future_path(candle(0, close=100, high=100.2, low=98.5))
    assert settle_path(tp, "LONG", 100, 99, 101)["outcome"] == "TP_FIRST"
    assert settle_path(sl, "LONG", 100, 99, 101)["outcome"] == "SL_FIRST"
    assert settle_path(tp, "LONG", 100, 99, 101)["gross_r"] == 1
    assert settle_path(sl, "LONG", 100, 99, 101)["gross_r"] == -1


def test_intrabar_ambiguity_never_counts_as_win():
    both = future_path(candle(0, close=100, high=102, low=98))
    out = settle_path(both, "LONG", 100, 99, 101, cost_bps=17)
    assert out["outcome"] == "AMBIGUOUS_INTRABAR_ORDER"
    assert out["gross_r"] is None and out["modeled_net_r"] is None


def test_gap_at_entry_invalidates_frozen_plan():
    gap = future_path(candle(0, close=98.5, open_price=98.5, high=100, low=98))
    out = settle_path(gap, "LONG", 100, 99, 101)
    assert out["outcome"] == "GAP_UNEXECUTABLE"
    assert out["gross_r"] is None


def test_costs_are_only_scenarios_and_not_assumed():
    tp = future_path(candle(0, close=100, high=101.5, low=99.8))
    unknown = settle_path(tp, "LONG", 100, 99, 101)
    estimated = settle_path(tp, "LONG", 100, 99, 101, cost_bps=17)
    assert unknown["modeled_net_r"] is None
    assert estimated["modeled_net_r"] == .83
    assert estimated["modeled_cost_only_not_venue_validated"]


def test_full_cohort_and_research_safety():
    bars = history()
    result = build_ledger("BTCUSDT", bars, bars, bars[-1]["close_time"], modeled_cost_bps=17)
    assert result["schema"] == SCHEMA
    assert result["research_only"] and not result["can_override_production"]
    assert not result["can_create_trade"] and not result["profitability_validated"]
    assert result["live_execution"] is False
    pairs = {}
    for item in result["rows"]:
        pairs.setdefault(item["event_at_ms"], set()).add(item["direction"])
        assert item["eligible_for_paper_portfolio"] is False
        assert item["forward_matures_at_ms"] <= bars[-1]["close_time"]
    assert len(pairs) > 1
    assert all(sides == {"LONG", "SHORT"} for sides in pairs.values())
    assert result["overlapping_event_outcomes_not_independent"]


def test_features_cannot_see_future_outcomes():
    bars = history()
    changed = copy.deepcopy(bars)
    # All post-observation candles can change; the frozen features/plan cannot.
    for c in changed[31:]:
        c["high"] = max(c["high"], c["open"] + 20)
        c["low"] = min(c["low"], c["open"] - 20)
    result_a = build_ledger("BTCUSDT", bars, bars, bars[-1]["close_time"])
    result_b = build_ledger("BTCUSDT", changed, bars, bars[-1]["close_time"])
    for a, b in zip(result_a["rows"][:2], result_b["rows"][:2]):
        assert a["features"] == b["features"]
        assert a["frozen_plan"] == b["frozen_plan"]
        assert a["event_at_ms"] == b["event_at_ms"]


def test_immature_future_never_labelled():
    bars = history()
    as_of = bars[49]["close_time"]
    x = build_ledger("ETHUSDT", bars, bars, as_of)
    assert x["market_observation_count"] == 50
    assert x["rows"]
    assert all(row["forward_matures_at_ms"] <= as_of for row in x["rows"])


def test_missing_aligned_btc_fails_closed():
    bars = history()
    btc_shifted = [dict(x, time=x["time"] + HOUR_MS // 2,
                         close_time=x["close_time"] + HOUR_MS // 2) for x in bars]
    result = build_ledger("ETHUSDT", bars, btc_shifted, btc_shifted[-1]["close_time"])
    assert result["rows"] == []
    assert result["skipped_no_aligned_btc"] > 0


def test_candle_gaps_rejected():
    bars = history()
    bars.pop(8)
    try:
        normalize_candles(bars, bars[-1]["close_time"])
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected contiguous-data safety guard")


if __name__ == "__main__":
    test_first_touch_tp_and_sl()
    test_intrabar_ambiguity_never_counts_as_win()
    test_gap_at_entry_invalidates_frozen_plan()
    test_costs_are_only_scenarios_and_not_assumed()
    test_full_cohort_and_research_safety()
    test_features_cannot_see_future_outcomes()
    test_immature_future_never_labelled()
    test_missing_aligned_btc_fails_closed()
    test_candle_gaps_rejected()
    print("edge event ledger v1 regression: ok")
