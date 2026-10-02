#!/usr/bin/env python3
"""Evidence-only Trade Quality Challenger V2.

Combines frozen-at-entry Production provenance with settled path outcomes to
rank candidate entry-quality cohorts. It never changes Production.
"""
from __future__ import annotations
import datetime as dt, json
from collections import defaultdict
from pathlib import Path

VERSION="ATLAS_TRADE_QUALITY_CHALLENGER_V2"
MIN_FROZEN_ROWS=30
MIN_COHORT_N=8

def _read(p): return json.loads(p.read_text(encoding="utf-8"))

def _key(r):
    p=r.get("decision_provenance") or {}
    a=p.get("score_attribution") or {}
    return {
      "htf_alignment":p.get("htf_alignment_class") or "UNKNOWN",
      "futures_alignment":p.get("futures_alignment") or "UNKNOWN",
      "extension_guard":a.get("extension_guard_reason") or "UNKNOWN",
      "regime":p.get("market_regime") or "UNKNOWN",
      "playbook":p.get("playbook") or "UNKNOWN",
    }

def _stats(rows):
    rs=[float(x["r_multiple"]) for x in rows if x.get("r_multiple") is not None]
    gross_win=sum(x for x in rs if x>0); gross_loss=-sum(x for x in rs if x<0)
    return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(sum(rs)/len(rs),4) if rs else None,
            "win_rate_pct":round(100*sum(x>0 for x in rs)/len(rs),2) if rs else None,
            "profit_factor_r":round(gross_win/gross_loss,4) if gross_loss else None}

def build(root:Path):
    src=_read(root/"status/production-failure-attribution-latest.json")
    rows=[r for r in src.get("rows") or [] if r.get("evidence_quality")=="PATH_PLUS_FROZEN_DECISION_PROVENANCE"]
    dimensions=("htf_alignment","futures_alignment","extension_guard","regime","playbook")
    cohorts={}
    for dim in dimensions:
        g=defaultdict(list)
        for r in rows: g[_key(r)[dim]].append(r)
        cohorts[dim]=[{"value":k,**_stats(v),"evidence_state":"ELIGIBLE_FOR_PROSPECTIVE_TEST" if len(v)>=MIN_COHORT_N else "INSUFFICIENT_SAMPLE"} for k,v in sorted(g.items())]
    losses=[r for r in rows if (r.get("r_multiple") or 0)<0]
    immediate=[r for r in losses if r.get("primary_attribution")=="IMMEDIATE_ADVERSE_MOVE"]
    follow=[r for r in losses if r.get("primary_attribution")=="INSUFFICIENT_FOLLOW_THROUGH_THEN_REVERSAL"]
    ready=len(rows)>=MIN_FROZEN_ROWS
    return {
      "schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
      "source":"status/production-failure-attribution-latest.json",
      "decision_source_of_truth":"FINAL_TRADE_GATE","product_horizon":"4-12H",
      "sample":{"frozen_rows":len(rows),"minimum_frozen_rows":MIN_FROZEN_ROWS,"formal_model_ready":ready},
      "baseline":_stats(rows),
      "failure_profile":{"losses":len(losses),"immediate_adverse":len(immediate),"insufficient_follow_through_then_reversal":len(follow)},
      "cohorts":cohorts,
      "promotion_policy":{"state":"COLLECTING" if not ready else "READY_FOR_PREREGISTERED_WALK_FORWARD",
        "required_validation":"STRICT_FORWARD_OUT_OF_SAMPLE","minimum_cohort_n":MIN_COHORT_N,
        "required_metrics":["net_r","avg_r","profit_factor_r","max_drawdown"],
        "no_retrospective_veto":True,"no_threshold_tuning":True},
      "safety":{"research_only":True,"paper_only":True,"live_execution":False,"production_impact":"NONE",
        "can_override_production":False,"can_change_threshold":False,"production_threshold":68,
        "can_create_trade":False,"can_veto_trade":False,"automatic_strategy_change":False},
      "interpretation":"DIAGNOSTIC_COHORTS_ARE_HYPOTHESES_NOT_CAUSAL_RULES"
    }

def validate(x):
    s=x["safety"]
    assert x["decision_source_of_truth"]=="FINAL_TRADE_GATE"
    assert s["research_only"] and not s["live_execution"] and s["production_impact"]=="NONE"
    assert not s["can_override_production"] and not s["can_change_threshold"]
    assert not s["can_create_trade"] and not s["can_veto_trade"] and not s["automatic_strategy_change"]
    assert s["production_threshold"]==68
    assert x["promotion_policy"]["required_validation"]=="STRICT_FORWARD_OUT_OF_SAMPLE"
    assert x["promotion_policy"]["no_threshold_tuning"] is True

if __name__=="__main__":
    root=Path(__file__).resolve().parent
    x=build(root);validate(x)
    out=root/"status/trade-quality-challenger-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"sample":x["sample"],"baseline":x["baseline"],"failure_profile":x["failure_profile"]},sort_keys=True))
