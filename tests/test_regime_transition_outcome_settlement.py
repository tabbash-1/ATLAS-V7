import datetime as dt
import regime_transition_outcome_settlement as s

def obs():
    return {"observation_id":"x","decision_id":"d","symbol":"ETHUSDT","captured_at":"2026-09-20T00:00:00+00:00",
      "candidate_direction":"LONG","challenger":{"eligible":True,"decision":"LONG"},
      "frozen_evidence":{"entry":100.0,"stop_loss":98.0,"tp2":104.0}}

def test_no_frozen_geometry_fails_closed():
    x=obs(); x["frozen_evidence"].pop("stop_loss")
    assert s.settle_one(x,dt.datetime(2026,9,21,tzinfo=dt.timezone.utc))["status"]=="NO_FROZEN_GEOMETRY"

def test_ineligible_never_settles_market():
    x=obs(); x["challenger"]["eligible"]=False
    assert s.settle_one(x,dt.datetime(2026,9,21,tzinfo=dt.timezone.utc))["status"]=="INELIGIBLE"

def test_cost_is_deducted_and_both_hit_is_stop_first(monkeypatch):
    candles=[{"open_time":int(dt.datetime(2026,9,20,tzinfo=dt.timezone.utc).timestamp()*1000),"high":105.0,"low":97.0,"close":101.0}]
    monkeypatch.setattr(s,"market_klines",lambda *a:(candles,"TEST"))
    r=s.settle_one(obs(),dt.datetime(2026,9,21,tzinfo=dt.timezone.utc))
    assert r["terminal_12h"]["event"]=="BOTH_HIT_STOP_FIRST"
    assert r["terminal_12h"]["net_r_after_cost"] < -1.0
