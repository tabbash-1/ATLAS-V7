#!/usr/bin/env python3
"""Profitability-first audit using only frozen entry-time features and cost-adjusted outcomes.

This module is research-only. It identifies pre-entry cohorts worth prospective
testing; it cannot create/veto trades or change Production.
"""
from __future__ import annotations
import json, datetime as dt
from collections import defaultdict
from pathlib import Path

VERSION="ATLAS_PROFITABILITY_ENTRY_AUDIT_V1"

def _f(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def build(root: Path):
    p=json.loads((root/"status/production-validation-latest.json").read_text())
    costs={r.get("decision_id"):r for r in (p.get("post_v2_cost_adjusted") or {}).get("rows") or []}
    rows=[]
    for r in p.get("rows") or []:
        prov=r.get("decision_provenance")
        if not isinstance(prov,dict) or prov.get("frozen_before_outcome") is not True:
            continue
        c=costs.get(r.get("decision_id") or r.get("id"))
        if not c: continue
        net=_f(c.get("net_r"))
        if net is None: continue
        a=prov.get("score_attribution") or {}
        rows.append({
            "decision_id":r.get("decision_id") or r.get("id"),
            "symbol":r.get("symbol"),"direction":r.get("direction"),"net_r":net,
            "score":_f(prov.get("score")),"htf_v2_eligible":prov.get("htf_v2_eligible"),
            "htf_alignment_class":prov.get("htf_alignment_class"),
            "futures_alignment":prov.get("futures_alignment"),
            "continuation_strong":prov.get("continuation_strong"),
            "breakout_confirmed":prov.get("breakout_confirmed"),
            "extension_guard_reason":a.get("extension_guard_reason"),
            "relative_strength_reason":a.get("relative_strength_reason"),
            "relative_volume":_f(prov.get("relative_volume")),
            "playbook":prov.get("playbook"),"market_regime":prov.get("market_regime"),
        })
    def cohort(name, pred):
        z=[x for x in rows if pred(x)]
        pos=[x for x in z if x["net_r"]>0]; neg=[x for x in z if x["net_r"]<=0]
        net=sum(x["net_r"] for x in z)
        gp=sum(x["net_r"] for x in pos); gl=-sum(x["net_r"] for x in neg)
        return {"name":name,"n":len(z),"positive":len(pos),
                "positive_rate_pct":round(100*len(pos)/len(z),2) if z else None,
                "net_r":round(net,4),"avg_net_r":round(net/len(z),4) if z else None,
                "profit_factor_r":round(gp/gl,4) if gl>0 else (None if not z else "INF"),
                "decision_ids":[x["decision_id"] for x in z]}
    cohorts=[
        cohort("ALL_FROZEN",lambda x:True),
        cohort("LONG",lambda x:x["direction"]=="LONG"),
        cohort("SHORT",lambda x:x["direction"]=="SHORT"),
        cohort("HTF_V2_ELIGIBLE",lambda x:x["htf_v2_eligible"] is True),
        cohort("HTF_V2_INELIGIBLE",lambda x:x["htf_v2_eligible"] is False),
        cohort("LONG_HTF_V2_ELIGIBLE",lambda x:x["direction"]=="LONG" and x["htf_v2_eligible"] is True),
        cohort("LONG_HTF_V2_INELIGIBLE",lambda x:x["direction"]=="LONG" and x["htf_v2_eligible"] is False),
        cohort("FUTURES_ALIGNED",lambda x:x["futures_alignment"]=="ALIGNED"),
        cohort("FUTURES_OPPOSED",lambda x:x["futures_alignment"]=="OPPOSED"),
        cohort("CONTINUATION_STRONG",lambda x:x["continuation_strong"] is True),
        cohort("RSI_SANE",lambda x:x["extension_guard_reason"]=="RSI_SANE"),
        cohort("HIGH_SCORE_90_PLUS",lambda x:(x["score"] or 0)>=90),
    ]
    # Pre-registered next hypothesis: HTF eligibility may discriminate profitable
    # LONG breakouts. This is observation only until a fresh prospective sample.
    h={x["name"]:x for x in cohorts}
    hypothesis={
        "id":"LONG_HTF_V2_ELIGIBILITY_PROFITABILITY",
        "feature_known_before_entry":True,
        "observation":{
            "eligible":h["LONG_HTF_V2_ELIGIBLE"],
            "ineligible":h["LONG_HTF_V2_INELIGIBLE"],
        },
        "candidate_rule":"Study LONG trades with htf_v2_eligible=true versus otherwise identical canonical LONG opportunities.",
        "falsification":"Reject as a profitability filter if fresh prospective cost-adjusted Net R / expectancy does not improve without unacceptable opportunity loss.",
        "production_action":"NONE",
    }
    return {
        "schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":"status/production-validation-latest.json",
        "metric":"COST_ADJUSTED_NET_R","rows":rows,"cohorts":cohorts,
        "next_profitability_hypothesis":hypothesis,
        "interpretation":{"profitability_proven":False,"promotion_allowed":False,
          "reason":"SMALL_SAMPLE; USE AS PROSPECTIVE HYPOTHESIS ONLY"},
        "safety":{"research_only":True,"paper_only":True,"uses_only_frozen_entry_features":True,
          "can_override_production":False,"can_create_trade":False,"can_veto_trade":False,
          "automatic_strategy_change":False}
    }

def validate(x):
    s=x["safety"]
    assert s["research_only"] and s["uses_only_frozen_entry_features"]
    assert not s["can_override_production"] and not s["can_create_trade"] and not s["can_veto_trade"]
    assert x["metric"]=="COST_ADJUSTED_NET_R"

if __name__=="__main__":
    root=Path(__file__).resolve().parent
    x=build(root);validate(x)
    out=root/"status/profitability-entry-audit-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"ok":True,"cohorts":x["cohorts"],"hypothesis":x["next_profitability_hypothesis"]["id"]},sort_keys=True))
