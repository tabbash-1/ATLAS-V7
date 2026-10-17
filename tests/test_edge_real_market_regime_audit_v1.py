"""Closed-market 90d audit: deterministic offline research regression suite."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.edge_event_ledger_v1 import HOUR_MS, build_ledger
from research.edge_real_market_regime_audit_v1 import (
    SCHEMA, _stats, _btc_regime, _extension_regime, _volatility_regime,
    build_market_audit, summarize, SYMBOLS,
)


def candles(days, final_time, slope=.08):
    n=days*24
    start=final_time+1-n*HOUR_MS
    out=[]
    for i in range(n):
        close=100+i*slope
        out.append({
            "time":start+i*HOUR_MS,
            "close_time":start+(i+1)*HOUR_MS-1,
            "open":close,
            "high":close+1,
            "low":close-1,
            "close":close,
            "volume":500 + i%12,
        })
    return out


def fake_fetch(symbol, days, as_of):
    if symbol not in SYMBOLS:
        raise AssertionError("Invalid symbol")
    rows=candles(days,as_of,-.03 if symbol=="ETHUSDT" else .03)
    return rows,{"symbol":symbol,"bars":len(rows),"continuity_validated":True}


def test_offline_60d_three_assets_does_not_fit_model_or_mutate_production():
    as_of=24*60*HOUR_MS-1
    report=build_market_audit(("BTCUSDT","ETHUSDT","SOLUSDT"),60,as_of,17,fake_fetch)
    assert report["schema"] == SCHEMA
    assert report["research_only"] is True
    assert report["profitability_validated"] is False
    assert report["can_change_production"] is False
    assert report["can_override_final_trade_gate"] is False
    assert report["can_create_trade"] is False
    assert report["model_comparison"]["model_fitted"] is False
    assert report["model_comparison"]["winner_selected"] is False
    assert report["model_comparison"]["strategies_tuned_from_outcomes"] is False
    assert report["model_comparison"]["split"]["purged_asset_time_events"]>0
    for name, stats in report["overall_holdout"].items():
        assert stats["decisions"]>0, name
        assert stats["decisions"] >= stats["valid_settlements"]
        assert stats["sum_modeled_net_r_nonexecuted"] is not None
    assert set(report["overall_holdout"]) == {
        "MOMENTUM_4H","REVERSAL_4H","BTC_ALIGNED_4H","HTF_ALIGNED_12H"}


def test_regime_is_from_frozen_observation_not_future():
    f={"btc_return_12h_pct":-1,"extension_atr_from_20h_mean":1.6,"atr_pct":1.5}
    assert _btc_regime(f)=="BTC_DOWN"
    assert _extension_regime(f)=="EXTENDED"
    assert _volatility_regime(f)=="ATR_GE_1PCT"


def test_ambiguous_never_counts_positive():
    row={"settlement":{"gross_r":None,"modeled_net_r":None}}
    s=_stats([row])
    assert s["decisions"]==1
    assert s["valid_settlements"]==0
    assert s["excluded_ambiguous_or_gap"]==1
    assert s["positive"]==0
    assert s["mean_modeled_net_r"] is None


def test_paired_data_and_calendar_purge():
    t=24*70*HOUR_MS-1
    btc=candles(60,t)
    a=build_ledger("BTCUSDT",btc,btc,t,17)
    result=summarize([a],70)
    assert result["split"]["purge_hours_before_holdout"]==24
    assert result["split"]["purged_asset_time_events"]>0
    assert result["by_segment"]["holdout"]["MOMENTUM_4H"]["BTC_UP"]["decisions"]>0
    assert "ASSET_NORMAL" in result["by_segment"]["holdout"]["MOMENTUM_4H"] or "ASSET_EXTENDED" in result["by_segment"]["holdout"]["MOMENTUM_4H"]


def test_refuse_partial_data_or_unapproved_hypothesis():
    t=24*60*HOUR_MS-1
    def incomplete(symbol,days,asof):
        bars,meta=fake_fetch(symbol,days,asof)
        if symbol=="ETHUSDT":
            return bars[:-1],meta
        return bars,meta
    try:
        build_market_audit(("BTCUSDT","ETHUSDT"),60,t,17,incomplete)
    except ValueError as e:
        assert "Unverified" in str(e)
    else:
        raise AssertionError("No silent time holes")
    try:
        build_market_audit(("BTCUSDT","HYPEUSDT"),60,t,17,fake_fetch)
    except ValueError as e:
        assert "Unsupported" in str(e)
    else:
        raise AssertionError("HYPE spot route unsupported by source")


if __name__=="__main__":
    test_offline_60d_three_assets_does_not_fit_model_or_mutate_production()
    test_regime_is_from_frozen_observation_not_future()
    test_ambiguous_never_counts_positive()
    test_paired_data_and_calendar_purge()
    test_refuse_partial_data_or_unapproved_hypothesis()
    print("90d market regime audit research tests: ok")
