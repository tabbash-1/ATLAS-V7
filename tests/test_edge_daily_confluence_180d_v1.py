"""Strict causal 1D aggregation, frozen Edge row matching and research firewall."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from research.edge_event_ledger_v1 import HOUR_MS
from research.edge_daily_confluence_180d_v1 import (
    DAY_MS, SCHEMA, POLICIES, SEGMENTS, completed_daily_from_hourly,
    daily_by_observation, aligned_segment, run,
)


def market(days, asof, incline=.03):
    start=asof+1-days*24*HOUR_MS
    return [{
        "time":start+i*HOUR_MS,
        "close_time":start+(i+1)*HOUR_MS-1,
        "open":110+incline*i,
        "high":110+incline*i+.65,
        "low":110+incline*i-.65,
        "close":110+incline*i,
        "volume":1000+i%20,
    } for i in range(days*24)]


def fetcher(symbol,days,asof):
    if symbol=="BTCUSDT":k=.03
    elif symbol=="ETHUSDT":k=-.014
    else:k=.008
    rows=market(days,asof,k)
    return rows,{"symbol":symbol,"bars":len(rows),"continuity_validated":True}


def test_daily_excludes_open_utc_day():
    # 180d begins at an arbitrary hour, causing an incomplete first/last
    # UTC calendar day; the aggregation must never synthesize partial days.
    asof=195*DAY_MS + 5*HOUR_MS -1
    rows=market(180,asof)
    daily=completed_daily_from_hourly(rows)
    assert len(daily)==179
    assert daily[-1]["close_time"]<asof
    assert all(d["close_time"]%DAY_MS==DAY_MS-1 for d in daily)
    assert all(d["open_time"]%DAY_MS==0 for d in daily)
    ts=daily[-1]["close_time"]+3*HOUR_MS
    states,_=daily_by_observation(rows,[ts,daily[-1]["close_time"]-1])
    assert states[ts]["last_closed_day_end_ms"]==daily[-1]["close_time"]
    assert states[daily[-1]["close_time"]-1]["last_closed_day_end_ms"]<=ts-DAY_MS


def test_daily_gap_or_invalid_time_fails_closed():
    asof=200*DAY_MS-1
    rows=market(180,asof)
    bad=[dict(row) for row in rows]
    bad[42]["time"]+=100
    try:
        completed_daily_from_hourly(bad)
    except ValueError:
        pass
    else:raise AssertionError("Misaligned hourly input must fail")
    bad=[dict(row) for row in rows]
    bad[42]["close_time"]+=100
    try:
        completed_daily_from_hourly(bad)
    except ValueError:
        pass
    else:raise AssertionError("Malformed 1h close must fail")


def test_alignment_categories():
    assert aligned_segment({"bias":"LONG"},"LONG")=="DAILY_ALIGNED"
    assert aligned_segment({"bias":"LONG"},"SHORT")=="DAILY_COUNTER"
    assert aligned_segment({"bias":"SHORT"},"LONG")=="DAILY_COUNTER"
    assert aligned_segment({"bias":"SHORT"},"SHORT")=="DAILY_ALIGNED"
    assert aligned_segment({"bias":"NEUTRAL"},"LONG")=="DAILY_NEUTRAL"
    assert aligned_segment(None,"LONG")=="DAILY_HISTORY_UNAVAILABLE"


def test_180d_realistic_causal_pair_splits():
    asof=210*DAY_MS-1
    result=run(("BTCUSDT","ETHUSDT","SOLUSDT"),180,asof,fetcher)
    assert result["schema"]==SCHEMA
    assert result["daily_definition"]=="ONLY_24_COMPLETED_UTC_1H_CANDLES"
    assert result["daily_filter_can_be_promoted"] is False
    assert result["can_change_production"] is False
    assert result["can_override_final_trade_gate"] is False
    assert result["can_create_trade"] is False
    assert result["profitability_validated"] is False
    assert result["holdout_already_exposed_by_prior_90d_research"] is True
    assert result["policy_or_filter_selected_based_on_outcomes"] is False
    assert result["all_phases_checked_before_promotion"] is True
    assert set(result["all_three_12h_nonoverlap_phases"])=={"0","1","2"}
    assert result["split"]["purged_asset_events"]>0
    assert result["split"]["daily_history_not_yet_mature_asset_events"]>0
    for phase,periods in result["all_three_12h_nonoverlap_phases"].items():
        for part in ("discovery","holdout"):
            for policy in POLICIES:
                groups=periods[part][policy]
                all_n=groups["ALL"]["selected"]
                sub_n=sum(groups[s]["selected"] for s in SEGMENTS)
                assert all_n==sub_n, (phase,part,policy)
                assert all_n>0
                for segment in ("ALL",)+SEGMENTS:
                    x=groups[segment]
                    assert x["settled"]+x["excluded_ambiguous_or_unexecutable"]==x["selected"]


def test_freeze_does_not_know_future_day():
    asof=180*DAY_MS-1
    candles=market(180,asof,.01)
    last=completed_daily_from_hourly(candles)[-1]["close_time"]
    # One *valid* newly closed hour from the next UTC day is not a
    # completed daily candle. It must not shift the daily context.
    future={**candles[-1],"time":asof+1,"close_time":asof+HOUR_MS}
    extended=candles+[future]
    assert completed_daily_from_hourly(extended)==completed_daily_from_hourly(candles)
    states,_=daily_by_observation(extended,[asof+HOUR_MS])
    assert states[asof+HOUR_MS]["last_closed_day_end_ms"]==last


if __name__=="__main__":
    test_daily_excludes_open_utc_day()
    test_daily_gap_or_invalid_time_fails_closed()
    test_alignment_categories()
    test_180d_realistic_causal_pair_splits()
    test_freeze_does_not_know_future_day()
    print("Edge 1D alignment 180d regression tests: ok")
