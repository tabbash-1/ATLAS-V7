import json
from direction_state_forward_shadow import capture

def test_missing_btc_features_fail_closed(tmp_path):
    s={"captured_at":"2026-10-02T00:00:00Z","decisions":{"BTCUSDT":{"ok":True,"candidate_direction":"LONG"},"ETHUSDT":{"ok":True,"candidate_direction":"LONG"}}}
    sp=tmp_path/"s.json";sp.write_text(json.dumps(s));hp=tmp_path/"h.jsonl"
    x=capture(str(sp),str(hp))["observation"]
    assert x["state"]=="MISSING_EVIDENCE"
    assert x["can_override_production"] is False
    assert x["live_execution"] is False
    assert "BTC_RSI14" in x["missing_evidence"]

def test_same_t0_features_and_prior_capture_only(tmp_path):
    hp=tmp_path/"h.jsonl"
    def run(t,rsi,mom,long_n,short_n):
        ds={"BTCUSDT":{"ok":True,"candidate_direction":"LONG","rsi14":rsi,"momentum_24h_pct":mom,"trend":"BULLISH"}}
        for i in range(long_n-1):ds[f"L{i}"]={"ok":True,"candidate_direction":"LONG"}
        for i in range(short_n):ds[f"S{i}"]={"ok":True,"candidate_direction":"SHORT"}
        sp=tmp_path/"s.json";sp.write_text(json.dumps({"captured_at":t,"decisions":ds}))
        return capture(str(sp),str(hp))["observation"]
    a=run("t1",79,2.5,7,1)
    b=run("t2",70,1.2,2,6)
    assert a["exhaustion"]["eligible"] is True
    assert b["previous_bullish_ratio"]==a["bullish_ratio"]
    assert b["reversal"]["eligible"] is True
