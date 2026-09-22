from regime_transition_frozen_evidence import freeze

def snap(regime=True):
    def d(sym):
        x={"ok":True,"candidate_direction":"LONG","canonical_decision":{"source_of_truth":"FINAL_TRADE_GATE","trade_ready":False,"decision_id":sym,"raw_wait_reason":"HTF_CONFLICT"},
           "htf_thesis":{"frames":{"1h":{"bias":"LONG"},"4h":{"bias":"LONG"},"12h":{"bias":"NEUTRAL"},"1d":{"bias":"NEUTRAL"}}},
           "geometry_gate":{"qualified":True},"trade_plan":{"rr_tp2":2.2,"entry":100.0,"stop_loss":99.0,"tp2":102.2},"futures_available":True,"futures_direction":"LONG","futures_provider":"TEST"}
        if regime:
            x["independent_market_regime"]={"regime":"TREND_UP"}
            x["independent_btc_regime"]={"regime":"BREAKOUT_UP"}
        return x
    return {"captured_at":"2026-09-21T12:00:00+00:00","decisions":{"BTCUSDT":d("btc"),"ETHUSDT":d("eth"),"SOLUSDT":d("sol")}}

def test_frozen_snapshot_can_qualify_only_with_present_evidence():
    rows=freeze(snap(True)); eth=next(x for x in rows if x["symbol"]=="ETHUSDT")
    assert eth["challenger"]["eligible"] is True
    assert eth["frozen_evidence"]["breadth"]["aligned_ratio"]==1.0
    assert eth["frozen_evidence"]["btc_regime"]["regime"]=="BREAKOUT_UP"\n    assert eth["frozen_evidence"]["net_rr_after_locked_cost"] > 2.0
    assert eth["can_override_production"] is False

def test_missing_independent_regime_fails_closed_not_recomputed():
    rows=freeze(snap(False)); eth=next(x for x in rows if x["symbol"]=="ETHUSDT")
    assert eth["challenger"]["eligible"] is False
    assert "ASSET_REGIME_NOT_ALIGNED" in eth["challenger"]["blockers"]
    assert eth["frozen_evidence"]["asset_regime"] is None
