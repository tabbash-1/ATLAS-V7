import profitability_ev_plan_replay as m

def test_ev_gate_requires_real_edge_and_sample():
    assert not m.ev_gate({"n":7,"avg_r":0.5,"profit_factor_r":2})["positive_ev_evidence"]
    assert not m.ev_gate({"n":10,"avg_r":-0.1,"profit_factor_r":0.9})["positive_ev_evidence"]
    assert m.ev_gate({"n":10,"avg_r":0.2,"profit_factor_r":1.3})["positive_ev_evidence"]

def test_plan_never_promotes_wait():
    x=m.manual_trade_plan({"action":"WAIT","execution_ready":False,"entry":10,"stop_loss":9,"tp1":11,"tp2":12,"rr_tp2":2,"score":70})
    assert x["decision"]=="WAIT" and x["complete"] is False and x["manual_execution_only"]

def test_replay_kpis_measure_capture_and_latency():
    x=m.replay_kpis([
      {"settled":True,"tradeable_opportunity":True,"atlas_captured":True,"detection_latency_min":15,"entry_efficiency":0.7},
      {"settled":True,"tradeable_opportunity":True,"atlas_captured":False,"detection_latency_min":40},
      {"settled":True,"tradeable_opportunity":False,"atlas_captured":False},
    ])
    assert x["opportunity_capture_rate"]==0.5
    assert x["avg_detection_latency_min"]==27.5
    assert x["avg_entry_efficiency"]==0.7
    s=m.safety()
    assert not s["can_create_trade"] and not s["can_override_production"] and s["production_threshold"]==68
