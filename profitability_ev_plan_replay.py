"""ATLAS Profitability stages 5-7: EV gate, executable manual plan, replay KPIs.

Evidence/shadow only until prospective sample is sufficient. FINAL_TRADE_GATE
remains the sole Production decision source.
"""
from __future__ import annotations
VERSION="ATLAS_PROFITABILITY_EV_PLAN_REPLAY_V1"

def expectancy(win_rate, avg_win_r, avg_loss_r):
    if win_rate is None or avg_win_r is None or avg_loss_r is None: return None
    p=max(0.0,min(1.0,float(win_rate)))
    return p*float(avg_win_r)-(1-p)*abs(float(avg_loss_r))

def ev_gate(cohort, min_n=8):
    c=cohort or {}; n=int(c.get("n") or 0)
    avg_r=c.get("avg_r"); pf=c.get("profit_factor_r")
    proven=n>=min_n and avg_r is not None and float(avg_r)>0 and pf is not None and float(pf)>1
    return {"evidence_n":n,"minimum_n":min_n,"avg_r":avg_r,"profit_factor_r":pf,
            "positive_ev_evidence":proven,
            "state":"ELIGIBLE_FOR_FORWARD_SHADOW" if proven else "INSUFFICIENT_OR_NONPOSITIVE_EDGE"}

def manual_trade_plan(row):
    r=row or {}; action=str(r.get("action") or "WAIT").upper()
    ready=bool(r.get("execution_ready") or r.get("trade_ready"))
    plan={"decision":action,"entry":r.get("entry"),"stop_loss":r.get("stop_loss"),
          "tp1":r.get("tp1"),"tp2":r.get("tp2"),"rr":r.get("rr_tp2") or r.get("risk_reward"),
          "confidence":r.get("score"),"invalidation":r.get("invalidation"),
          "expected_holding":"4-12H","manual_execution_only":True}
    plan["complete"]=action in {"LONG","SHORT"} and ready and all(plan.get(k) is not None for k in ("entry","stop_loss","tp1","tp2","rr"))
    return plan

def replay_kpis(events):
    xs=list(events or []); settled=[x for x in xs if x.get("settled")]
    opportunities=[x for x in settled if x.get("tradeable_opportunity")]
    captured=[x for x in opportunities if x.get("atlas_captured")]
    lat=[float(x["detection_latency_min"]) for x in opportunities if x.get("detection_latency_min") is not None]
    eff=[float(x["entry_efficiency"]) for x in captured if x.get("entry_efficiency") is not None]
    return {"settled":len(settled),"tradeable_opportunities":len(opportunities),"captured":len(captured),
            "opportunity_capture_rate":round(len(captured)/len(opportunities),4) if opportunities else None,
            "avg_detection_latency_min":round(sum(lat)/len(lat),2) if lat else None,
            "avg_entry_efficiency":round(sum(eff)/len(eff),4) if eff else None}

def safety():
    return {"research_only":True,"paper_only":True,"live_execution":False,
            "can_create_trade":False,"can_override_production":False,
            "can_change_threshold":False,"production_threshold":68,
            "decision_source_of_truth":"FINAL_TRADE_GATE",
            "promotion_requires":"STRICT_FORWARD_OUT_OF_SAMPLE"}
