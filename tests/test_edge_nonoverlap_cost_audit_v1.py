"""No-network regression for 12h nonoverlap, as-of semantics and costs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from research.edge_event_ledger_v1 import HOUR_MS, build_ledger
from research.edge_nonoverlap_cost_audit_v1 import (
    SCHEMA, COST_BPS, prepare_event_rows, _evaluate, compare, run,
)


def candles(days, as_of_ms, slope=.02):
    start=as_of_ms+1-days*24*HOUR_MS
    return [{
        "time":start+i*HOUR_MS,
        "close_time":start+(i+1)*HOUR_MS-1,
        "open":100+slope*i, "high":101+slope*i,
        "low":99+slope*i, "close":100+slope*i, "volume":200+i%10,
    } for i in range(days*24)]


def fetcher(symbol, days, as_of):
    data=candles(days,as_of,-.01 if symbol=="ETHUSDT" else .01)
    return data, {"symbol":symbol,"bars":len(data),"continuity_validated":True}


def test_run_nonoverlap_dependent_assets_and_all_costs():
    asof=80*24*HOUR_MS-1
    report=run(["BTCUSDT","ETHUSDT","SOLUSDT"],60,asof,fetcher)
    assert report["schema"]==SCHEMA
    assert report["split"]["per_symbol_12h_path_overlap"] is False
    assert report["split"]["cross_symbol_btc_shock_dependence"] is True
    assert report["split"]["purged_asset_events"]>0
    assert report["research_only"] and not report["can_change_production"]
    assert report["can_create_trade"] is False
    assert report["profitability_validated"] is False
    assert report["reused_historical_holdout_not_blind"] is True
    for section in ("discovery","holdout"):
        for policy,metrics in report["periods"][section].items():
            assert metrics["settled"]>0, (section,policy)
            assert set(metrics["cost_scenarios"])=={str(k) for k in COST_BPS}
            # For a given set of fills and stops, extra positive fees cannot
            # improve the modeled net R.
            means=[metrics["cost_scenarios"][str(k)]["mean_net_r"] for k in COST_BPS]
            assert means==sorted(means,reverse=True)
            assert metrics["cost_scenarios"]["17"]["calendar_day_cluster_ci95_descriptive"] is not None


def test_cannot_count_ambiguous_intrabar():
    d={"settlement":{"gross_r":None,"hypothetical_fill_open":None},
       "frozen_plan":{"stop_loss":99}}
    good={"settlement":{"gross_r":2,"hypothetical_fill_open":100},
          "frozen_plan":{"stop_loss":99},
          "event_at_ms":24*HOUR_MS-1}
    x=_evaluate([d,good])
    assert x["selected"]==2 and x["settled"]==1
    assert x["excluded_ambiguous_or_gap"]==1
    assert x["cost_scenarios"]["0"]["mean_net_r"]==2
    assert x["cost_scenarios"]["17"]["mean_net_r"]==1.83
    assert x["breakeven_roundtrip_bps_descriptive"]==200


def test_unpaired_and_unfrozen_events_rejected():
    asof=80*24*HOUR_MS-1
    rows=candles(60,asof)
    ledger=build_ledger("BTCUSDT",rows,rows,asof)
    assert ledger["rows"]
    selected,info=prepare_event_rows([ledger])
    assert info["nonoverlap_12h_timestamps"] > 15
    # Separate selected events for each symbol must never be 4h apart.
    for side in selected:
        for policy in selected[side]:
            ts=sorted(r["event_at_ms"] for r in selected[side][policy])
            assert all(b-a>=12*HOUR_MS for a,b in zip(ts,ts[1:]))


def test_provider_completeness_fail_closed():
    asof=80*24*HOUR_MS-1
    def bad(symbol, days, end):
        rows, quality=fetcher(symbol,days,end)
        if symbol=="ETHUSDT":
            return rows[:-1],quality
        return rows,quality
    try:
        run(["BTCUSDT","ETHUSDT"],60,asof,bad)
    except ValueError as e:
        assert "incomplete" in str(e)
    else:
        raise AssertionError("Incomplete fetched input must fail closed")


if __name__=="__main__":
    test_run_nonoverlap_dependent_assets_and_all_costs()
    test_cannot_count_ambiguous_intrabar()
    test_unpaired_and_unfrozen_events_rejected()
    test_provider_completeness_fail_closed()
    print("edge nonoverlap cost audit tests: ok")
