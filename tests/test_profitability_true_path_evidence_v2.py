import math
import profitability_true_path_evidence_v2 as v

def test_locked_costs_and_net_r():
 assert v.TOTAL_COST_R==0.04
 assert v.net_r(1)==1.96
 assert v.net_r(0)==-1.04

def test_brier_and_logloss_are_reported():
 m=v.metrics([.8,.2],[1,0]);assert m["n"]==2;assert abs(m["brier"]-.04)<1e-12;assert m["log_loss"]>0

def test_purge_embargo_temporal_isolation():
 h=3600000;rows=[{"t":i*h} for i in range(100)];s=v.temporal_split(rows)
 assert s["train"][-1]["t"]<=s["train_boundary"]-12*h
 assert s["validation"][0]["t"]>=s["train_boundary"]+12*h
 assert s["validation"][-1]["t"]<=s["validation_boundary"]-12*h
 assert s["test"][0]["t"]>=s["validation_boundary"]+12*h

def test_safety_keeps_production_locked():
 s=v.safety();assert s["threshold"]==68;assert s["production_impact"]=="NONE";assert s["costs_locked"] is True;assert s["can_override_final_gate"] is False
