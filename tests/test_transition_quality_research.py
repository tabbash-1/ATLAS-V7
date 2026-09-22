from transition_quality_research import assess

def obs(**kw):
    x={"candidate_direction":"LONG","frozen_evidence":{
      "frames":{"1h":{"bias":"LONG"},"4h":{"bias":"LONG"},"12h":{"bias":"LONG"},"1d":{"bias":"NEUTRAL"}},
      "asset_regime":{"regime":"TREND_UP"},"btc_regime":{"regime":"VOLATILITY_EXPANSION_UP"},
      "derivatives":{"direction":"LONG","crowded":False},"breadth":{"aligned_ratio":.8},
      "net_rr_after_locked_cost":2.05}}
    x["frozen_evidence"].update(kw); return x

def test_full_t0_quality_is_research_eligible():
    r=assess(obs()); assert r["eligible"] and r["decision"]=="LONG"
    assert r["can_override_production"] is False and r["live_execution"] is False

def test_derivatives_opposition_blocks():
    r=assess(obs(derivatives={"direction":"SHORT","crowded":False}))
    assert not r["eligible"] and "DERIVATIVES_OPPOSE" in r["blockers"]

def test_missing_net_rr_fails_closed():
    r=assess(obs(net_rr_after_locked_cost=None))
    assert not r["eligible"] and "NET_RR_BELOW_2_OR_MISSING" in r["blockers"]

def test_4h_neutral_blocks():
    f=obs()["frozen_evidence"]["frames"]; f["4h"]={"bias":"NEUTRAL"}
    r=assess(obs(frames=f)); assert not r["eligible"] and "4H_NOT_ALIGNED" in r["blockers"]

def test_daily_opposition_blocks():
    f=obs()["frozen_evidence"]["frames"]; f["1d"]={"bias":"SHORT"}
    r=assess(obs(frames=f)); assert not r["eligible"] and "1D_OPPOSES" in r["blockers"]
