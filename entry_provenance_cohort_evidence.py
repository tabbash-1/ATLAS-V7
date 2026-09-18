#!/usr/bin/env python3
"""ATLAS frozen-entry provenance cohort evidence.

Prospective evidence only. Compares settled post-V2 FINAL_TRADE_GATE paper
outcomes by decision features that were frozen before the outcome was known.
It can nominate hypotheses for a separate shadow test, but cannot change
Production or claim causal root causes.
"""
from __future__ import annotations
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION="ATLAS_ENTRY_PROVENANCE_COHORT_EVIDENCE_V1"
SOURCE_SCHEMA="ATLAS_PRODUCTION_VALIDATION_SCORECARD_V1"
PROVENANCE_SCHEMA="ATLAS_ENTRY_DECISION_PROVENANCE_V1"
EPOCH_ID="HTF_SR_V2_2026-09-14"
THRESHOLD=68
MIN_TOTAL_PROVENANCE=30
MIN_BUCKET_N=10
MIN_COMPLEMENT_N=10
MIN_ABS_DELTA_R=0.25

DIMENSIONS=(
    "direction","score_margin_bucket","htf_alignment_class","htf_regime",
    "breakout_confirmed","continuation_strong","futures_alignment",
    "entry_mode","scenario_readiness","setup_quality_status","playbook","market_regime",
)


def _read(p: Path) -> dict[str,Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _f(v):
    try: return float(v)
    except Exception: return None


def _score_bucket(score, threshold):
    s=_f(score); t=_f(threshold)
    if s is None or t is None: return "UNKNOWN"
    m=s-t
    if m <= 0: return "MARGIN_LE_0"
    if m <= 5: return "MARGIN_0_TO_5"
    if m <= 15: return "MARGIN_5_TO_15"
    return "MARGIN_GT_15"


def _valid_provenance(row: dict[str,Any]) -> bool:
    p=row.get("decision_provenance")
    return bool(
        isinstance(p,dict)
        and p.get("schema") == PROVENANCE_SCHEMA
        and p.get("frozen_before_outcome") is True
        and p.get("strategy_epoch_id") == EPOCH_ID
        and p.get("product_horizon") == "4-12H"
        and p.get("production_threshold_locked") == 68
    )


def _horizon_end(captured_at):
    try:
        x=dt.datetime.fromisoformat(str(captured_at).replace("Z","+00:00"))
        if x.tzinfo is None: x=x.replace(tzinfo=dt.timezone.utc)
        return (x+dt.timedelta(hours=12)).isoformat()
    except Exception:
        return None


def _feature_row(row: dict[str,Any], cost_map: dict[str,dict[str,Any]]) -> dict[str,Any] | None:
    p=row.get("decision_provenance")
    s=row.get("settlement") or {}
    did=str(row.get("decision_id") or row.get("id") or "")
    if not _valid_provenance(row):
        return None
    if s.get("terminal") is not True or not did: return None
    cost=cost_map.get(did) or {}
    gross=_f(s.get("r_multiple")); net=_f(cost.get("net_r"))
    if gross is None or net is None: return None
    def val(k, fallback=None):
        x=p.get(k)
        return fallback if x is None else x
    return {
        "decision_id":did,"symbol":row.get("symbol"),"direction":str(row.get("direction") or "UNKNOWN").upper(),
        "captured_at":row.get("captured_at"),"gross_r":gross,"net_r":net,
        "score":_f(p.get("score")),"threshold":_f(p.get("threshold")) or THRESHOLD,
        "score_margin_bucket":_score_bucket(p.get("score"),p.get("threshold") or THRESHOLD),
        "htf_alignment_class":str(val("htf_alignment_class","UNKNOWN")),
        "htf_regime":str(val("htf_regime","UNKNOWN")),
        "breakout_confirmed":str(val("breakout_confirmed","UNKNOWN")),
        "continuation_strong":str(val("continuation_strong","UNKNOWN")),
        "futures_alignment":str(val("futures_alignment","UNKNOWN")),
        "entry_mode":str(val("entry_mode","UNKNOWN")),
        "scenario_readiness":str(val("scenario_readiness","UNKNOWN")),
        "setup_quality_status":str(val("setup_quality_status","UNKNOWN")),
        "playbook":str(val("playbook","UNKNOWN")),
        "market_regime":str(val("market_regime","UNKNOWN")),
    }


def _stats(rows):
    rs=[float(x["net_r"]) for x in rows]
    gross=[float(x["gross_r"]) for x in rows]
    pos=sum(x for x in rs if x>0); neg=abs(sum(x for x in rs if x<0))
    return {"n":len(rows),"net_r":round(sum(rs),4) if rs else None,
            "avg_net_r":round(sum(rs)/len(rs),4) if rs else None,
            "avg_gross_r":round(sum(gross)/len(gross),4) if gross else None,
            "positive_pct":round(100*sum(x>0 for x in rs)/len(rs),2) if rs else None,
            "profit_factor_r":round(pos/neg,4) if neg>0 else ("INF" if pos>0 else None)}


def _cohorts(rows):
    out={}
    for dim in DIMENSIONS:
        groups=defaultdict(list)
        for r in rows: groups[str(r.get(dim,"UNKNOWN"))].append(r)
        out[dim]={k:_stats(v) for k,v in sorted(groups.items())}
    return out


def _hypotheses(rows, cohorts):
    if len(rows) < MIN_TOTAL_PROVENANCE: return []
    out=[]
    for dim in DIMENSIONS:
        for value,st in cohorts.get(dim,{}).items():
            bucket=[r for r in rows if str(r.get(dim,"UNKNOWN"))==value]
            comp=[r for r in rows if str(r.get(dim,"UNKNOWN"))!=value]
            if len(bucket)<MIN_BUCKET_N or len(comp)<MIN_COMPLEMENT_N: continue
            a=_stats(bucket); b=_stats(comp)
            av=a.get("avg_net_r"); bv=b.get("avg_net_r")
            if not isinstance(av,(int,float)) or not isinstance(bv,(int,float)): continue
            delta=round(av-bv,4)
            kind=None
            if av < 0 and bv > 0 and delta <= -MIN_ABS_DELTA_R: kind="NEGATIVE_FEATURE_SHADOW_FILTER_CANDIDATE"
            elif av > 0 and bv < 0 and delta >= MIN_ABS_DELTA_R: kind="POSITIVE_FEATURE_SHADOW_COHORT_CANDIDATE"
            if kind:
                out.append({"dimension":dim,"value":value,"kind":kind,"bucket":a,"complement":b,
                            "delta_avg_net_r":delta,"action":"SHADOW_TEST_ONLY"})
    return sorted(out,key=lambda x:abs(float(x["delta_avg_net_r"])),reverse=True)


def build(root: Path):
    src=_read(root/"status/production-validation-latest.json")
    if src.get("schema")!=SOURCE_SCHEMA: raise RuntimeError("unexpected scorecard schema")
    if (src.get("epoch") or {}).get("id")!=EPOCH_ID: raise RuntimeError("unexpected epoch")
    if (src.get("safety") or {}).get("production_threshold")!=THRESHOLD: raise RuntimeError("threshold drift")
    if (src.get("safety") or {}).get("can_override_production") is not False: raise RuntimeError("source can override Production")
    cost_rows=((src.get("post_v2_cost_adjusted") or {}).get("rows") or [])
    cost_map={str(x.get("decision_id")):x for x in cost_rows if x.get("decision_id")}
    all_post_v2=list(src.get("rows") or [])
    all_terminal=[x for x in all_post_v2 if (x.get("settlement") or {}).get("terminal") is True]
    frozen_all=[x for x in all_post_v2 if _valid_provenance(x)]
    frozen_open=[x for x in frozen_all if (x.get("settlement") or {}).get("terminal") is not True]
    rows=[z for z in (_feature_row(x,cost_map) for x in all_terminal) if z is not None]
    pending=[{
        "decision_id":str(x.get("decision_id") or x.get("id") or ""),
        "symbol":x.get("symbol"),"direction":x.get("direction"),"captured_at":x.get("captured_at"),
        "settlement_status":(x.get("settlement") or {}).get("status"),
        "horizon_end_at":_horizon_end(x.get("captured_at")),
        "paper_only":True,
    } for x in frozen_open]
    cohorts=_cohorts(rows)
    hypotheses=_hypotheses(rows,cohorts)
    return {
        "schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "epoch":{"id":EPOCH_ID},"decision_source_of_truth":"FINAL_TRADE_GATE","product_horizon":"4-12H",
        "criteria_locked_before_evaluation":True,
        "criteria":{"min_total_provenance":MIN_TOTAL_PROVENANCE,"min_bucket_n":MIN_BUCKET_N,
                    "min_complement_n":MIN_COMPLEMENT_N,"min_abs_delta_avg_net_r":MIN_ABS_DELTA_R,
                    "dimensions":list(DIMENSIONS),"cost_adjusted_metric":"net_r"},
        "coverage":{"post_v2_entries":len(all_post_v2),"terminal_post_v2":len(all_terminal),
                    "frozen_provenance_entries_total":len(frozen_all),
                    "frozen_provenance_open":len(frozen_open),"frozen_provenance_terminal":len(rows),
                    "path_only_terminal":len(all_terminal)-len(rows),
                    "terminal_coverage_pct":round(100*len(rows)/len(all_terminal),2) if all_terminal else None,
                    "formal_total_ready":len(rows)>=MIN_TOTAL_PROVENANCE,
                    "remaining_to_formal_total":max(0,MIN_TOTAL_PROVENANCE-len(rows))},
        "pending_frozen_entries":pending,
        "state":"FORMAL_PROVENANCE_COHORT_SAMPLE_READY" if len(rows)>=MIN_TOTAL_PROVENANCE else "COLLECTING_FROZEN_ENTRY_PROVENANCE",
        "overall":_stats(rows),"cohorts":cohorts,"shadow_test_hypotheses":hypotheses,
        "rows":rows,
        "interpretation":{"root_cause_claim_allowed":False,"automatic_strategy_change":False,
                          "automatic_shadow_deploy":False,"multiple_testing_warning":True,
                          "hypotheses_are_causal_proof":False,
                          "next_step":"COLLECT_PROSPECTIVE_PROVENANCE" if len(rows)<MIN_TOTAL_PROVENANCE else "REVIEW_PRELOCKED_SHADOW_HYPOTHESES"},
        "safety":{"research_only":True,"paper_only":True,"live_execution":False,"production_impact":"NONE",
                  "can_override_production":False,"can_change_threshold":False,"production_threshold":68,
                  "score_logic_changed":False,"risk_logic_changed":False,"sl_tp_logic_changed":False,
                  "final_trade_gate_changed":False},
    }


def validate(p):
    assert p.get("schema")==VERSION
    assert p.get("criteria_locked_before_evaluation") is True
    assert p.get("decision_source_of_truth")=="FINAL_TRADE_GATE"
    assert p.get("epoch",{}).get("id")==EPOCH_ID
    assert p.get("safety",{}).get("production_threshold")==68
    assert p.get("safety",{}).get("production_impact")=="NONE"
    assert p.get("safety",{}).get("can_override_production") is False
    assert p.get("interpretation",{}).get("root_cause_claim_allowed") is False
    for r in p.get("rows") or []:
        assert r.get("net_r") is not None and r.get("gross_r") is not None


def main():
    root=Path(__file__).resolve().parent
    p=build(root); validate(p)
    out=root/"status/entry-provenance-cohort-latest.json"
    out.write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"state":p["state"],"coverage":p["coverage"],
                      "hypotheses":len(p["shadow_test_hypotheses"]),"out":str(out)}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
