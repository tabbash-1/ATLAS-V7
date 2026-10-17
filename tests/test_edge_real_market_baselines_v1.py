"""Tests for the real-market Edge baseline pipeline. No network required."""
from pathlib import Path
import io
import json
import sys
import urllib.error
import urllib.parse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.edge_real_market_baselines_v1 import (
    HOUR_MS, VERSION, asof_last_closed_hour, fetch_completed_1h,
    compare_baselines, _policy_direction,
)
from research.edge_event_ledger_v1 import build_ledger


def candles(days, as_of, step=.04):
    start=as_of+1-days*24*HOUR_MS
    bars=[]
    for i in range(days*24):
        p=100 + i*step
        bars.append({
            "time":start+i*HOUR_MS,"close_time":start+(i+1)*HOUR_MS-1,
            "open":p, "high":p+.5,"low":p-.5,"close":p,
            "volume":100+i*.1,
        })
    return bars


class Provider:
    def __init__(self, rows, fail_first=False):
        self.rows=rows
        self.fail_first=fail_first
        self.calls=[]
    def __call__(self, url, timeout=18):
        self.calls.append(url)
        if self.fail_first and "provider-a" in url:
            raise urllib.error.HTTPError(url, 451, "blocked", None, None)
        query=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        assert query["interval"]==["1h"]
        low=int(query["startTime"][0]); high=int(query["endTime"][0]); limit=int(query["limit"][0])
        chosen=[x for x in self.rows if low<=x["time"]<=high][:limit]
        encoded=[[x["time"],str(x["open"]),str(x["high"]),str(x["low"]),
                  str(x["close"]),str(x["volume"]),x["close_time"]]
                 for x in chosen]
        return io.BytesIO(json.dumps(encoded).encode())


def test_utc_asof_hour_boundary():
    t=asof_last_closed_hour(1_800_000_000_000)
    assert (t+1)%HOUR_MS==0
    assert t<1_800_000_000_000
    assert t+HOUR_MS>=1_800_000_000_000


def test_fetch_exact_closed_pages_no_gaps():
    now=asof_last_closed_hour(1_800_000_000_000)
    bars=candles(55,now)
    provider=Provider(bars)
    seen,q=fetch_completed_1h("BTCUSDT",55,now,request_fn=provider,hosts=("https://provider-a",))
    assert seen==bars
    assert q["continuity_validated"] and q["bars"]==1320
    assert len(provider.calls)==2
    assert q["last_close_ms"]==now


def test_fallback_and_hard_fail_on_missing_market_hours():
    asof=asof_last_closed_hour(1_800_000_000_000)
    bars=candles(15,asof)
    provider=Provider(bars,fail_first=True)
    observed,q=fetch_completed_1h("ETHUSDT",15,asof,request_fn=provider,
                                  hosts=("https://provider-a","https://provider-b"))
    assert observed==bars
    assert q["data_providers_used"]==["https://provider-b"]
    broken=Provider(bars[:100]+bars[101:])
    try:
        fetch_completed_1h("BTCUSDT",15,asof,request_fn=broken,hosts=("https://provider-b",))
    except ValueError as exc:
        assert "missing" in str(exc).lower() or "truncated" in str(exc).lower()
    else:
        raise AssertionError("Missing market history must fail closed")


def test_invalid_symbol_and_asof_are_rejected():
    asof=asof_last_closed_hour(1_800_000_000_000)
    p=Provider(candles(15,asof))
    for symbol,stamp in [("FAKEUSDT",asof),("BTCUSDT",asof+1)]:
        try:
            fetch_completed_1h(symbol,15,stamp,request_fn=p,hosts=("https://provider",))
        except ValueError:
            pass
        else:
            raise AssertionError("Input must be rejected")


def test_paired_purged_train_holdout_baselines():
    asof=asof_last_closed_hour(1_800_000_000_000)
    btc=candles(30,asof)
    asset=candles(30,asof,step=-.01)
    ledger=build_ledger("ETHUSDT",asset,btc,asof,17)
    report=compare_baselines([ledger],train_ratio=.7)
    assert report["winner_selected_from_holdout"] is False
    assert report["predictive_probabilities_calibrated"] is False
    assert report["net_production_pnl_claim"] is False
    assert report["unique_timestamp_counts"]["holdout"]>0
    assert report["unique_timestamp_counts"]["discovery"]>0
    assert report["purged_asset_time_events"]>0
    assert set(report["scores"]["holdout"])=={
        "MOMENTUM_4H","REVERSAL_4H","BTC_ALIGNED_4H","HTF_ALIGNED_12H"}
    assert report["scores"]["holdout"]["BTC_ALIGNED_4H"]["selected"]==0
    assert report["scores"]["holdout"]["MOMENTUM_4H"]["selected"]>0


def test_policy_uses_pre_entry_features():
    f={"asset_return_4h_pct":-2.0,"btc_return_4h_pct":-1.0,
       "asset_return_12h_pct":1.0,"btc_return_12h_pct":-1.0}
    assert _policy_direction("MOMENTUM_4H",f)=="SHORT"
    assert _policy_direction("REVERSAL_4H",f)=="LONG"
    assert _policy_direction("BTC_ALIGNED_4H",f)=="SHORT"
    assert _policy_direction("HTF_ALIGNED_12H",f) is None


if __name__=="__main__":
    test_utc_asof_hour_boundary()
    test_fetch_exact_closed_pages_no_gaps()
    test_fallback_and_hard_fail_on_missing_market_hours()
    test_invalid_symbol_and_asof_are_rejected()
    test_paired_purged_train_holdout_baselines()
    test_policy_uses_pre_entry_features()
    print("edge real market baseline tests: ok")
