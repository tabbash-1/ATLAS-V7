#!/usr/bin/env python3
"""ATLAS Evidence & Performance Control Center aggregator.

Read-only product observability over committed GitHub Actions evidence.
No scoring, threshold, risk, trade-plan, or execution authority.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

VERSION="ATLAS_EVIDENCE_CONTROL_CENTER_V1"
EPOCH_ID="HTF_SR_V2_2026-09-14"
THRESHOLD=68
FORMAL_SAMPLE=30


def _load(root: Path, name: str) -> dict[str,Any]:
    p=root/"status"/name
    try:
        x=json.loads(p.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) else {}
    except Exception:
        return {}


def _pct(n,d):
    return round(100*n/d,2) if d else None


def build(root: Path) -> dict[str,Any]:
    v=_load(root,"production-validation-latest.json")
    a=_load(root,"production-failure-attribution-latest.json")
    c=_load(root,"entry-provenance-cohort-latest.json")
    w=_load(root,"wait-missed-opportunity-latest.json")
    p=_load(root,"paper-portfolio-10k-latest.json")
    o=_load(root,"canonical-outcomes-latest.json")
    r=_load(root,"opportunity-replay-shadow-latest.json")
    pr=_load(root,"opportunity-path-replay-latest.json")
    sg=_load(root,"strategy-change-review-gate-latest.json")
    if (v.get("epoch") or {}).get("id") not in (None,EPOCH_ID):
        raise RuntimeError("control center refuses mixed strategy epoch")
    if (v.get("safety") or {}).get("production_threshold") not in (None,THRESHOLD):
        raise RuntimeError("control center refuses threshold drift")

    gross=v.get("post_v2") or {}
    net=v.get("post_v2_cost_adjusted") or {}
    coverage=c.get("coverage") or {}
    entries=int(gross.get("entries") or 0)
    terminal=int(gross.get("terminal") or 0)
    provenance_terminal=int(coverage.get("frozen_provenance_terminal") or 0)
    rows=[]
    cost={str(x.get("decision_id")):x for x in net.get("rows") or [] if x.get("decision_id")}
    attr={str(x.get("decision_id")):x for x in a.get("rows") or [] if x.get("decision_id")}
    for x in v.get("rows") or []:
        did=str(x.get("decision_id") or x.get("id") or "")
        s=x.get("settlement") or {}; g=x.get("geometry") or {}
        cc=cost.get(did) or {}; aa=attr.get(did) or {}
        rows.append({
            "decision_id":did,"symbol":x.get("symbol"),"direction":x.get("direction"),
            "captured_at":x.get("captured_at"),"score":x.get("score"),"threshold":x.get("threshold"),
            "entry":g.get("entry"),"stop_loss":g.get("stop_loss"),"tp1":g.get("tp1"),"tp2":g.get("tp2"),
            "status":s.get("status"),"gross_r":s.get("r_multiple"),"net_r":cc.get("net_r"),
            "net_pnl_usd":cc.get("net_pnl_usd"),"mfe_r":s.get("mfe_r"),"mae_r":s.get("mae_r"),
            "time_to_mfe_peak_h":s.get("time_to_mfe_peak_h"),"time_to_tp1_h":s.get("time_to_tp1_h"),
            "attribution":aa.get("primary_attribution"),"attribution_tags":aa.get("secondary_tags") or [],
            "evidence_quality":aa.get("evidence_quality"),
        })

    wait_post=(w.get("cohorts") or {}).get("post_v2_forward") or {}
    if not wait_post and isinstance(w.get("post_v2_forward"),dict): wait_post=w.get("post_v2_forward")
    return {
        "schema":VERSION,"epoch_id":EPOCH_ID,"product_horizon":"4-12H",
        "decision_source_of_truth":"FINAL_TRADE_GATE","production_threshold":THRESHOLD,
        "headline":{
            "entries":entries,"terminal":terminal,"positive":gross.get("positive"),"negative":gross.get("negative"),
            "gross_net_r":gross.get("net_r"),"gross_pnl_usd":gross.get("paper_pnl_usd"),
            "cost_adjusted_net_r":net.get("net_r"),"cost_adjusted_pnl_usd":net.get("net_pnl_usd"),
            "profit_factor_net":net.get("profit_factor_r"),"max_drawdown_pct_net":net.get("max_drawdown_pct"),
            "estimated_cost_usd":net.get("estimated_total_cost_usd"),
        },
        "sample_progress":{
            "trade_outcomes":{"current":terminal,"required":FORMAL_SAMPLE,"pct":_pct(terminal,FORMAL_SAMPLE),
                              "remaining":max(0,FORMAL_SAMPLE-terminal),"ready":terminal>=FORMAL_SAMPLE},
            "frozen_provenance":{"current":provenance_terminal,"required":FORMAL_SAMPLE,"pct":_pct(provenance_terminal,FORMAL_SAMPLE),
                                 "remaining":max(0,FORMAL_SAMPLE-provenance_terminal),"ready":provenance_terminal>=FORMAL_SAMPLE},
        },
        "funnel":{
            "paper_entries":entries,"terminal_outcomes":terminal,
            "tp1_reached":gross.get("tp1_reached"),"tp2_wins":gross.get("tp2_wins"),
            "wait_post_v2_matured":wait_post.get("matured") or wait_post.get("records"),
            "wait_post_v2_missed":wait_post.get("missed"),
            "wait_post_v2_missed_rate_pct":wait_post.get("missed_rate_pct") or wait_post.get("rate_pct"),
        },
        "direction":net.get("by_direction") or {},
        "failure_attribution":a.get("summary") or {},
        "opportunity_replay":{"schema":r.get("schema"),"activation_at":r.get("activation_at"),
                              "eligible_prospective_rows":r.get("eligible_prospective_rows",0),
                              "hypotheses":r.get("hypotheses") or [],
                              "automatic_strategy_change":False},
        "path_replay":{"schema":pr.get("schema"),"activation_at":pr.get("activation_at"),
                       "eligible_prospective_rows":pr.get("eligible_prospective_rows",0),
                       "market_data_errors":len(pr.get("market_data_errors") or []),
                       "hypotheses":pr.get("hypotheses") or [],
                       "automatic_strategy_change":False,"best_variant_selection_allowed":False},
        "strategy_review_gate":{"schema":sg.get("schema"),"overall_decision":sg.get("overall_decision") or "PRESERVE_CURRENT_PRODUCTION",
                                "eligible_for_manual_review":sg.get("eligible_for_manual_review") or [],
                                "criteria":sg.get("criteria") or {},"hypotheses":sg.get("hypotheses") or [],
                                "automatic_promotion":False,"production_impact":"NONE"},
        "provenance":{
            "state":c.get("state"),"coverage":coverage,"overall":c.get("overall") or {},
            "shadow_test_hypotheses":c.get("shadow_test_hypotheses") or [],
            "automatic_strategy_change":False,
        },
        "rows":rows,
        "freshness":{
            "validation_generated_at":v.get("generated_at"),"attribution_generated_at":a.get("generated_at"),
            "provenance_generated_at":c.get("generated_at"),"paper_generated_at":p.get("generated_at"),
            "canonical_outcomes_generated_at":o.get("generated_at"),
        },
        "safety":{"research_only":True,"paper_only":True,"live_execution":False,"production_impact":"NONE",
                  "can_override_production":False,"can_change_threshold":False,"automatic_promotion":False},
    }


def validate(x):
    assert x["schema"]==VERSION
    assert x["epoch_id"]==EPOCH_ID
    assert x["production_threshold"]==68
    assert x["decision_source_of_truth"]=="FINAL_TRADE_GATE"
    assert x["safety"]["production_impact"]=="NONE"
    assert x["safety"]["can_override_production"] is False
    assert x["provenance"]["automatic_strategy_change"] is False


def main():
    root=Path(__file__).resolve().parent
    x=build(root); validate(x)
    print(json.dumps(x,indent=2,sort_keys=True))
    return 0


if __name__=="__main__": raise SystemExit(main())
