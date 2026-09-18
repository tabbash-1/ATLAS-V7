#!/usr/bin/env python3
"""Evidence-locked manual review gate for future ATLAS strategy changes.

Consumes only pre-registered prospective Champion-vs-Shadow paired evidence.
It cannot alter Production. Passing means eligible for human/manual implementation
review, never automatic promotion.
"""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
from typing import Any

VERSION="ATLAS_STRATEGY_CHANGE_REVIEW_GATE_V1"
EPOCH_ID="HTF_SR_V2_2026-09-14"
ACTIVATION_AT="2026-09-18T07:10:00+00:00"
THRESHOLD=68
MIN_PAIRED_N=30
MIN_EFFECT_N=10
MIN_SEGMENT_N=10
MIN_DELTA_AVG_R=0.10
MIN_SHADOW_PF=1.10

CRITERIA={
 "paired_n":MIN_PAIRED_N,
 "affected_n":MIN_EFFECT_N,
 "chronological_segment_n":MIN_SEGMENT_N,
 "shadow_avg_net_r_gt":0.0,
 "delta_avg_net_r_gte":MIN_DELTA_AVG_R,
 "shadow_profit_factor_gte":MIN_SHADOW_PF,
 "shadow_max_drawdown_r_lte_champion":True,
 "early_delta_avg_r_gt":0.0,
 "late_delta_avg_r_gt":0.0,
}


def _load(root:Path,name:str):
    try:return json.loads((root/"status"/name).read_text(encoding="utf-8"))
    except Exception:return {}


def _metrics(vals):
    vals=[float(x) for x in vals]
    if not vals:return {"n":0,"sum_r":0.0,"avg_r":None,"profit_factor":None,"max_drawdown_r":None}
    gains=sum(x for x in vals if x>0); losses=-sum(x for x in vals if x<0)
    pf=(gains/losses) if losses>0 else (999.0 if gains>0 else None)
    eq=peak=0.0;dd=0.0
    for x in vals:
        eq+=x;peak=max(peak,eq);dd=max(dd,peak-eq)
    return {"n":len(vals),"sum_r":round(sum(vals),4),"avg_r":round(sum(vals)/len(vals),4),
            "profit_factor":round(pf,4) if pf is not None else None,"max_drawdown_r":round(dd,4)}


def _evaluate(hid,kind,rows):
    rows=sorted([x for x in rows if x.get("champion_net_r") is not None and x.get("shadow_net_r") is not None],
                key=lambda x:str(x.get("captured_at") or ""))
    n=len(rows); affected=[x for x in rows if x.get("policy_effect") not in (None,"UNCHANGED_CHAMPION_PATH")]
    champion=[float(x["champion_net_r"]) for x in rows]; shadow=[float(x["shadow_net_r"]) for x in rows]
    delta=[s-c for s,c in zip(shadow,champion)]
    cm=_metrics(champion); sm=_metrics(shadow); dm=_metrics(delta)
    half=n//2; early=delta[:half]; late=delta[half:]
    em=_metrics(early); lm=_metrics(late)
    checks={
      "paired_n":n>=MIN_PAIRED_N,
      "affected_n":len(affected)>=MIN_EFFECT_N,
      "shadow_positive_expectancy":sm["avg_r"] is not None and sm["avg_r"]>0,
      "delta_avg_net_r":dm["avg_r"] is not None and dm["avg_r"]>=MIN_DELTA_AVG_R,
      "shadow_profit_factor":sm["profit_factor"] is not None and sm["profit_factor"]>=MIN_SHADOW_PF,
      "drawdown_not_worse":sm["max_drawdown_r"] is not None and cm["max_drawdown_r"] is not None and sm["max_drawdown_r"]<=cm["max_drawdown_r"],
      "early_segment_n":em["n"]>=MIN_SEGMENT_N,
      "late_segment_n":lm["n"]>=MIN_SEGMENT_N,
      "early_delta_positive":em["avg_r"] is not None and em["avg_r"]>0,
      "late_delta_positive":lm["avg_r"] is not None and lm["avg_r"]>0,
    }
    passed=all(checks.values())
    return {"id":hid,"kind":kind,"paired_n":n,"affected_n":len(affected),
            "champion":cm,"shadow":sm,"delta":dm,"early_delta":em,"late_delta":lm,
            "checks":checks,"passed":passed,
            "decision":"ELIGIBLE_FOR_MANUAL_IMPLEMENTATION_REVIEW" if passed else ("INSUFFICIENT_PROSPECTIVE_SAMPLE" if n<MIN_PAIRED_N else "NO_STRATEGY_CHANGE"),
            "automatic_promotion":False,"production_impact":"NONE"}


def build(root:Path)->dict[str,Any]:
    filters=_load(root,"opportunity-replay-shadow-latest.json")
    paths=_load(root,"opportunity-path-replay-latest.json")
    if filters.get("activation_at") not in (None,ACTIVATION_AT) or paths.get("activation_at") not in (None,ACTIVATION_AT):
        raise RuntimeError("activation boundary mismatch")
    if (filters.get("safety") or {}).get("production_threshold") not in (None,THRESHOLD):raise RuntimeError("filter threshold drift")
    if (paths.get("safety") or {}).get("production_threshold") not in (None,THRESHOLD):raise RuntimeError("path threshold drift")
    out=[]
    for h in filters.get("hypotheses") or []:
        if h.get("kind")!="FILTER":continue
        out.append(_evaluate(h.get("id"),"FILTER",h.get("paired_rows") or []))
    for h in paths.get("hypotheses") or []:
        out.append(_evaluate(h.get("id"),"PATH_CHANGE",h.get("rows") or []))
    eligible=[x["id"] for x in out if x["passed"]]
    return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "epoch_id":EPOCH_ID,"activation_at":ACTIVATION_AT,"product_horizon":"4-12H",
            "criteria_locked_before_formal_sample":True,"criteria":CRITERIA,
            "hypotheses":out,"eligible_for_manual_review":eligible,
            "overall_decision":"MANUAL_IMPLEMENTATION_REVIEW_REQUIRED" if eligible else "PRESERVE_CURRENT_PRODUCTION",
            "interpretation":{"passing_is_not_proof_of_causality":True,"best_variant_selection_allowed":False,
                              "automatic_strategy_change":False,"automatic_promotion":False,
                              "future_semantic_change_requires_new_epoch":True},
            "safety":{"research_only":True,"paper_only":True,"live_execution":False,
                      "production_threshold":68,"can_override_production":False,"can_change_threshold":False,
                      "production_impact":"NONE"}}


def validate(x):
    assert x["schema"]==VERSION and x["criteria_locked_before_formal_sample"] is True
    assert x["safety"]["production_threshold"]==68 and x["safety"]["can_override_production"] is False
    assert x["interpretation"]["best_variant_selection_allowed"] is False
    assert all(h["automatic_promotion"] is False for h in x["hypotheses"])
    if x["overall_decision"]=="MANUAL_IMPLEMENTATION_REVIEW_REQUIRED":
        assert x["eligible_for_manual_review"]


def main():
    root=Path(__file__).resolve().parent;x=build(root);validate(x)
    out=root/"status/strategy-change-review-gate-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"decision":x["overall_decision"],"eligible":x["eligible_for_manual_review"],"out":str(out)}))
    return 0
if __name__=="__main__":raise SystemExit(main())
