"""ATLAS true-path Expected-R evaluation utilities V2.

Research shadow only. Labels use TP-before-SL / SL-before-TP after decision time.
Adds locked round-trip costs, probability calibration metrics and embargo helpers.
"""
from __future__ import annotations
import math
import profitability_trade_outcome_predictor as op

VERSION="ATLAS_TRUE_PATH_EV_V2"
HORIZON_HOURS=12
PURGE_HOURS=12
EMBARGO_HOURS=12
# Locked conservative research cost in R units. It represents combined fees +
# slippage for entry and exit and is deliberately not tuned per sample.
ROUND_TRIP_COST_R=0.04

def net_expected_r(p_tp,reward_r=2.0,risk_r=1.0,cost_r=ROUND_TRIP_COST_R):
    return float(p_tp)*reward_r-(1.0-float(p_tp))*risk_r-float(cost_r)

def realized_net_r(y,reward_r=2.0,risk_r=1.0,cost_r=ROUND_TRIP_COST_R):
    if y not in (0,1): return None
    return (reward_r if y==1 else -risk_r)-float(cost_r)

def calibration(rows):
    """rows: iterable of {p,y}; unresolved labels must be excluded upstream."""
    q=[z for z in rows if z.get("y") in (0,1)]
    if not q:return {"n":0,"brier":None,"log_loss":None}
    b=sum((float(z["p"])-int(z["y"]))**2 for z in q)/len(q)
    eps=1e-12
    ll=-sum(int(z["y"])*math.log(max(eps,min(1-eps,float(z["p"]))))+(1-int(z["y"]))*math.log(max(eps,min(1-eps,1-float(z["p"])))) for z in q)/len(q)
    return {"n":len(q),"brier":round(b,6),"log_loss":round(ll,6)}

def purged_fit(rows,cutoff_ms):
    boundary=int(cutoff_ms)-PURGE_HOURS*3600000
    return [z for z in rows if int(z["t"])<=boundary]

def embargoed_exam(rows,cutoff_ms):
    boundary=int(cutoff_ms)+EMBARGO_HOURS*3600000
    return [z for z in rows if int(z["t"])>boundary]

def score_model(model,rows):
    scored=[];unresolved=0
    for z in rows:
        y=z.get("y")
        if y not in (0,1):unresolved+=1;continue
        pred=op.predict(model,z["x"]);p=pred["p_tp_before_sl"]
        scored.append({"t":z["t"],"symbol":z.get("symbol"),"side":z.get("side"),"p":p,"y":y,
          "expected_r_gross":pred["expected_r"],"expected_r_net":net_expected_r(p),
          "realized_r_net":realized_net_r(y)})
    return {"rows":scored,"calibration":calibration(scored),"unresolved":unresolved,
      "cost_r":ROUND_TRIP_COST_R,"purge_hours":PURGE_HOURS,"embargo_hours":EMBARGO_HOURS}

def safety():
    return {"research_only":True,"production_impact":"NONE","threshold":68,
      "label":"TP_BEFORE_SL_PATH","same_candle":"LOSS","horizon_hours":HORIZON_HOURS,
      "purge_hours":PURGE_HOURS,"embargo_hours":EMBARGO_HOURS,
      "round_trip_cost_r":ROUND_TRIP_COST_R,"cost_locked":True,
      "can_override_final_gate":False,"automatic_promotion":False}
