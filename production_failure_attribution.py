#!/usr/bin/env python3
"""ATLAS post-V2 Production failure attribution.

Evidence-only diagnostic layer. It explains settled canonical FINAL_TRADE_GATE
paper outcomes without changing score, threshold, HTF gates, risk, SL/TP, or
execution. Existing post-V2 rows without frozen entry provenance are explicitly
marked PATH_ONLY rather than retroactively reconstructing decision context.
"""
from __future__ import annotations
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "ATLAS_PRODUCTION_FAILURE_ATTRIBUTION_V1"
SOURCE_SCHEMA = "ATLAS_PRODUCTION_VALIDATION_SCORECARD_V1"
EPOCH_ID = "HTF_SR_V2_2026-09-14"
THRESHOLD = 68.0


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _f(v):
    try: return float(v)
    except Exception: return None


def _checkpoint(row: dict[str, Any], h: int):
    for x in row.get("product_window_checkpoints") or []:
        if int(x.get("checkpoint_h") or 0) == h:
            return x
    return {}


def _hours_to_exit(row: dict[str, Any]):
    end = (row.get("settlement") or {}).get("exit_at_ms")
    start = row.get("captured_at_ms")
    if end is None or start is None: return None
    return round((float(end)-float(start))/3_600_000.0, 4)


def diagnose(row: dict[str, Any]) -> dict[str, Any]:
    s = row.get("settlement") or {}
    r = _f(s.get("r_multiple"))
    mfe = _f(s.get("mfe_r")); mae = _f(s.get("mae_r"))
    score = _f(row.get("score")); threshold = _f(row.get("threshold")) or THRESHOLD
    margin = None if score is None else round(score-threshold, 4)
    tp1 = bool(s.get("tp1_reached")); status = str(s.get("status") or "UNKNOWN")
    tte = _hours_to_exit(row)
    t_mfe=_f(s.get("time_to_mfe_peak_h")); t_mae=_f(s.get("time_to_mae_peak_h")); t_tp1=_f(s.get("time_to_tp1_h"))
    provenance = row.get("decision_provenance") if isinstance(row.get("decision_provenance"), dict) else None
    quality = "PATH_PLUS_FROZEN_DECISION_PROVENANCE" if provenance and provenance.get("frozen_before_outcome") is True else "PATH_ONLY"
    tags=[]

    if margin is not None:
        if margin <= 0: tags.append("MARGINAL_THRESHOLD_ENTRY")
        elif margin <= 5: tags.append("LOW_SCORE_MARGIN")
        else: tags.append("HIGH_SCORE_ENTRY")

    if r is not None and r < 0:
        if mfe is not None and mfe <= 0:
            primary="IMMEDIATE_ADVERSE_MOVE"
        elif mfe is not None and mfe < 1.0:
            primary="INSUFFICIENT_FOLLOW_THROUGH_THEN_REVERSAL"
        else:
            primary="FAVORABLE_EXCURSION_FAILED_TO_CONVERT"
        if tte is not None:
            if tte < 1: tags.append("STOP_WITHIN_1H")
            elif tte < 4: tags.append("STOP_WITHIN_4H")
            elif tte >= 8: tags.append("LATE_HORIZON_REVERSAL")
        if mae is not None and mae >= 1: tags.append("FULL_RISK_INVALIDATION")
        if mfe is not None and mfe >= .5 and t_mfe is not None and t_mfe <= 1: tags.append("EARLY_FAVORABLE_EXCURSION_THEN_REVERSAL")
        elif mfe is not None and mfe >= .5 and t_mfe is not None and t_mfe >= 4: tags.append("LATE_FAVORABLE_PEAK_THEN_REVERSAL")
    elif r is not None and r > 0:
        if status == "WIN_TP2":
            primary="POSITIVE_CONTROL_TP2"
        elif tp1:
            primary="PARTIAL_EDGE_NO_TP2"
        else:
            primary="POSITIVE_EXPIRED_WITHOUT_TP1"
    else:
        primary="FLAT_OR_UNRESOLVED"

    if provenance:
        if provenance.get("breakout_confirmed") is False: tags.append("ENTRY_WITHOUT_BREAKOUT_CONFIRMATION")
        if provenance.get("htf_alignment_class") not in (None, "ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"):
            tags.append("NONSTANDARD_HTF_ALIGNMENT")
        if provenance.get("futures_alignment") == "OPPOSED": tags.append("FUTURES_OPPOSED_AT_ENTRY")

    cps={str(h): _f(_checkpoint(row,h).get("r_multiple")) for h in (4,8,12)}
    return {
        "decision_id": row.get("decision_id") or row.get("id"),
        "symbol": row.get("symbol"), "direction": row.get("direction"),
        "captured_at": row.get("captured_at"), "score": score, "threshold": threshold,
        "score_margin": margin, "terminal_status": status, "r_multiple": r,
        "mfe_r": mfe, "mae_r": mae, "tp1_reached": tp1,
        "hours_to_terminal": tte, "time_to_mfe_peak_h":t_mfe,"time_to_mae_peak_h":t_mae,"time_to_tp1_h":t_tp1,
        "checkpoint_r": cps,
        "primary_attribution": primary, "secondary_tags": tags,
        "evidence_quality": quality,
        "decision_provenance": provenance,
    }


def _group(rows, key):
    out={}
    groups=defaultdict(list)
    for r in rows: groups[str(r.get(key) or "UNKNOWN")].append(r)
    for name,z in sorted(groups.items()):
        rs=[x["r_multiple"] for x in z if x.get("r_multiple") is not None]
        out[name]={"n":len(z),"net_r":round(sum(rs),4) if rs else None,
                   "avg_r":round(sum(rs)/len(rs),4) if rs else None,
                   "positive_pct":round(100*sum(x>0 for x in rs)/len(rs),2) if rs else None}
    return out


def build(root: Path) -> dict[str, Any]:
    src=_read(root/"status/production-validation-latest.json")
    if src.get("schema") != SOURCE_SCHEMA: raise RuntimeError("unexpected Production Validation schema")
    if (src.get("epoch") or {}).get("id") != EPOCH_ID: raise RuntimeError("unexpected performance epoch")
    if (src.get("safety") or {}).get("production_threshold") != 68: raise RuntimeError("production threshold drift")
    if (src.get("safety") or {}).get("can_override_production") is not False: raise RuntimeError("source can override Production")
    rows=[diagnose(x) for x in src.get("rows") or [] if (x.get("settlement") or {}).get("terminal") is True]
    causes=Counter(x["primary_attribution"] for x in rows)
    tags=Counter(t for x in rows for t in x["secondary_tags"])
    path_only=sum(x["evidence_quality"]=="PATH_ONLY" for x in rows)
    losses=[x for x in rows if (x.get("r_multiple") or 0)<0]
    return {
        "schema":VERSION,
        "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "epoch":{"id":EPOCH_ID,"terminal_rows":len(rows)},
        "decision_source_of_truth":"FINAL_TRADE_GATE",
        "product_horizon":"4-12H",
        "state":"COLLECTING_CAUSAL_EVIDENCE" if len(rows)<30 else "FORMAL_ATTRIBUTION_SAMPLE_READY",
        "evidence_quality":{"path_only_rows":path_only,"rows_with_frozen_entry_provenance":len(rows)-path_only,
                            "retroactive_provenance_inference_allowed":False},
        "summary":{"terminal":len(rows),"losses":len(losses),
                   "primary_attributions":dict(sorted(causes.items())),
                   "secondary_tags":dict(sorted(tags.items())),
                   "by_direction":_group(rows,"direction"),"by_symbol":_group(rows,"symbol")},
        "rows":rows,
        "interpretation":{
            "automatic_strategy_change":False,
            "root_cause_claim_allowed":False,
            "reason":"ENTRY_PROVENANCE_AND_SAMPLE_NOT_YET_SUFFICIENT" if path_only or len(rows)<30 else "FORMAL_REVIEW_REQUIRED",
            "current_rows_are_diagnostic_not_causal_proof":True,
        },
        "safety":{"research_only":True,"paper_only":True,"live_execution":False,
                  "production_impact":"NONE","can_override_production":False,
                  "can_change_threshold":False,"production_threshold":68,
                  "score_logic_changed":False,"risk_logic_changed":False,
                  "sl_tp_logic_changed":False,"final_trade_gate_changed":False},
    }


def validate(p: dict[str, Any]):
    assert p.get("schema")==VERSION
    assert p.get("decision_source_of_truth")=="FINAL_TRADE_GATE"
    assert p.get("epoch",{}).get("id")==EPOCH_ID
    assert p.get("safety",{}).get("production_threshold")==68
    assert p.get("safety",{}).get("production_impact")=="NONE"
    assert p.get("safety",{}).get("can_override_production") is False
    assert p.get("interpretation",{}).get("automatic_strategy_change") is False
    assert p.get("evidence_quality",{}).get("retroactive_provenance_inference_allowed") is False


def main():
    root=Path(__file__).resolve().parent
    p=build(root); validate(p)
    out=root/"status/production-failure-attribution-latest.json"
    out.write_text(json.dumps(p,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"ok":True,"state":p["state"],"terminal":p["summary"]["terminal"],
                      "losses":p["summary"]["losses"],"causes":p["summary"]["primary_attributions"],"out":str(out)}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
