#!/usr/bin/env python3
"""Pre-registered Opportunity Replay Shadow for ATLAS post-V2 evidence.

Evaluates only prospectively frozen entry context. Filter hypotheses answer:
"What would a shadow policy have done to the same canonical trade set?"
They do not alter Production and are not causal proof. Path-changing variants
(delay entry / fail-fast exit) are registered but remain NOT_EVALUABLE until a
separate candle-path replay implementation can settle them without lookahead.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from typing import Any

VERSION="ATLAS_OPPORTUNITY_REPLAY_SHADOW_V1"
EPOCH_ID="HTF_SR_V2_2026-09-14"
ACTIVATION_AT="2026-09-18T07:10:00+00:00"
THRESHOLD=68
MIN_N=30

HYPOTHESES=[
 {"id":"FUTURES_OPPOSITION_VETO","kind":"FILTER","rule":"futures_alignment == OPPOSED","shadow_action":"SKIP"},
 {"id":"BREAKOUT_CONFIRMATION_REQUIRED","kind":"FILTER","rule":"breakout_confirmed == False","shadow_action":"SKIP"},
 {"id":"MARGINAL_THRESHOLD_VETO","kind":"FILTER","rule":"score_margin <= 0","shadow_action":"SKIP"},
 {"id":"DELAY_ENTRY_1H_CONFIRM","kind":"PATH_CHANGE","rule":"delay entry until next closed 1H confirmation","shadow_action":"REPRICE_ENTRY"},
 {"id":"EARLY_MOMENTUM_FAILFAST_EXIT","kind":"PATH_CHANGE","rule":"exit early after predefined momentum failure","shadow_action":"REPRICE_EXIT"},
]


def _load(root,name):
    try:return json.loads((root/"status"/name).read_text(encoding="utf-8"))
    except Exception:return {}


def _iso(s):
    try:return dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
    except Exception:return None


def _trigger(h,p):
    if h=="FUTURES_OPPOSITION_VETO": return p.get("futures_alignment")=="OPPOSED"
    if h=="BREAKOUT_CONFIRMATION_REQUIRED": return p.get("breakout_confirmed") is False
    if h=="MARGINAL_THRESHOLD_VETO":
        try:return float(p.get("score"))-float(p.get("threshold") or THRESHOLD)<=0
        except Exception:return False
    return False


def build(root:Path)->dict[str,Any]:
    v=_load(root,"production-validation-latest.json")
    cost={str(x.get("decision_id")):x for x in (v.get("post_v2_cost_adjusted") or {}).get("rows") or []}
    activation=_iso(ACTIVATION_AT)
    eligible=[]
    for row in v.get("rows") or []:
        p=row.get("decision_provenance"); captured=_iso(row.get("captured_at"))
        did=str(row.get("decision_id") or row.get("id") or "")
        if not isinstance(p,dict) or p.get("frozen_before_outcome") is not True: continue
        if p.get("strategy_epoch_id")!=EPOCH_ID or p.get("product_horizon")!="4-12H": continue
        if not captured or captured<activation: continue
        cc=cost.get(did) or {}
        if cc.get("net_r") is None: continue
        eligible.append({"decision_id":did,"symbol":row.get("symbol"),"direction":row.get("direction"),
                         "captured_at":row.get("captured_at"),"net_r":float(cc["net_r"]),"provenance":p})
    results=[]
    for h in HYPOTHESES:
        if h["kind"]!="FILTER":
            results.append({**h,"state":"NOT_EVALUABLE_PATH_REPLAY_REQUIRED","n":0,
                            "promotion_allowed":False,"production_impact":"NONE"})
            continue
        kept=[x for x in eligible if not _trigger(h["id"],x["provenance"])]
        skipped=[x for x in eligible if _trigger(h["id"],x["provenance"])]
        paired_rows=[]
        for x in eligible:
            triggered=_trigger(h["id"],x["provenance"])
            shadow_r=0.0 if triggered else float(x["net_r"])
            paired_rows.append({"decision_id":x["decision_id"],"symbol":x["symbol"],"direction":x["direction"],
                                "captured_at":x["captured_at"],"champion_net_r":float(x["net_r"]),
                                "shadow_net_r":shadow_r,"delta_net_r":round(shadow_r-float(x["net_r"]),4),
                                "policy_effect":"SKIPPED_BY_SHADOW_POLICY" if triggered else "UNCHANGED_CHAMPION_PATH"})
        champion=sum(x["net_r"] for x in eligible); shadow=sum(x["shadow_net_r"] for x in paired_rows)
        results.append({**h,"state":"COLLECTING" if len(eligible)<MIN_N else "FORMAL_SHADOW_SAMPLE_READY",
                        "n":len(eligible),"kept":len(kept),"skipped":len(skipped),
                        "champion_net_r":round(champion,4),"shadow_filter_net_r":round(shadow,4),
                        "delta_net_r":round(shadow-champion,4),"min_n":MIN_N,
                        "formal_ready":len(eligible)>=MIN_N,"promotion_allowed":False,
                        "production_impact":"NONE","paired_rows":paired_rows})
    return {"schema":VERSION,"activation_at":ACTIVATION_AT,"epoch_id":EPOCH_ID,
            "criteria_locked_before_evaluation":True,"eligible_prospective_rows":len(eligible),
            "hypotheses":results,
            "interpretation":{"causal_claim_allowed":False,"best_variant_selection_allowed":False,
                              "automatic_strategy_change":False,"automatic_promotion":False,
                              "path_change_variants_require_candle_replay":True},
            "safety":{"research_only":True,"paper_only":True,"live_execution":False,
                      "can_override_production":False,"can_change_threshold":False,
                      "production_threshold":68,"production_impact":"NONE"}}


def validate(x):
    assert x["schema"]==VERSION and x["criteria_locked_before_evaluation"] is True
    assert x["safety"]["production_threshold"]==68
    assert x["safety"]["can_override_production"] is False
    assert x["interpretation"]["best_variant_selection_allowed"] is False
    assert all(h["promotion_allowed"] is False for h in x["hypotheses"])


def main():
    root=Path(__file__).resolve().parent;x=build(root);validate(x)
    out=root/"status/opportunity-replay-shadow-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"eligible":x["eligible_prospective_rows"],"out":str(out)}));return 0
if __name__=="__main__":raise SystemExit(main())
