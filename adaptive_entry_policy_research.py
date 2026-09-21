#!/usr/bin/env python3
"""ATLAS adaptive entry-policy research.

Post-hoc diagnostic only. Tests a simple two-speed entry policy on already-frozen
prospective decisions:
- strong frozen setups (score >= 80): keep Champion immediate entry;
- lower-score setups: require the existing first full post-decision 1H confirmation.

The score cut is motivated by prior cohort diagnostics and therefore MUST NOT be
treated as prospective proof. It never mutates Production.
"""
from __future__ import annotations
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
PATH=ROOT/"status/opportunity-path-replay-latest.json"
VAL=ROOT/"status/production-validation-latest.json"
OUT=ROOT/"status/adaptive-entry-policy-latest.json"
STRONG_SCORE=80.0

def _score_map(v):
    out={}
    for r in v.get("rows") or []:
        did=str(r.get("decision_id") or r.get("id") or "")
        p=r.get("decision_provenance") or {}
        if did and p.get("score") is not None:
            out[did]=float(p["score"])
    return out

def choose(champion_r, delayed_r, score):
    if champion_r is None or score is None:return None,"UNEVALUABLE"
    if score>=STRONG_SCORE:return float(champion_r),"IMMEDIATE_STRONG_SETUP"
    if delayed_r is None:return None,"UNEVALUABLE_DELAY_PATH"
    return float(delayed_r),"DELAY_1H_CONFIRM"

def build(path_report,validation):
    scores=_score_map(validation)
    delay=next((h for h in path_report.get("hypotheses") or [] if h.get("id")=="DELAY_ENTRY_1H_CONFIRM"),{})
    rows=[]
    for r in delay.get("rows") or []:
        did=str(r.get("decision_id") or "")
        c=r.get("champion_net_r"); d=r.get("shadow_net_r"); s=scores.get(did)
        adaptive,policy=choose(c,d,s)
        rows.append({"decision_id":did,"symbol":r.get("symbol"),"score":s,"champion_net_r":c,
                     "delayed_net_r":d,"adaptive_net_r":adaptive,"policy":policy})
    paired=[r for r in rows if r["adaptive_net_r"] is not None and r["champion_net_r"] is not None]
    champ=sum(float(r["champion_net_r"]) for r in paired)
    adapt=sum(float(r["adaptive_net_r"]) for r in paired)
    return {"schema":"ATLAS_ADAPTIVE_ENTRY_POLICY_RESEARCH_V1","product_horizon":"4-12H",
            "policy":{"strong_score_gte":STRONG_SCORE,"strong_action":"KEEP_IMMEDIATE_ENTRY",
                      "otherwise":"REQUIRE_FIRST_FULL_POST_DECISION_1H_DIRECTIONAL_CONFIRMATION"},
            "paired_n":len(paired),"champion_net_r":round(champ,4),"adaptive_net_r":round(adapt,4),
            "delta_net_r":round(adapt-champ,4),"rows":rows,
            "interpretation":{"post_hoc":True,"prospective_proof":False,"minimum_new_forward_sample":30,
                              "production_change_authorized":False},
            "safety":{"research_only":True,"paper_only":True,"live_execution":False,
                      "production_impact":"NONE","can_override_production":False}}

def main():
    x=build(json.loads(PATH.read_text()),json.loads(VAL.read_text()))
    OUT.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:x[k] for k in ("paired_n","champion_net_r","adaptive_net_r","delta_net_r")},sort_keys=True))
if __name__=="__main__":main()
