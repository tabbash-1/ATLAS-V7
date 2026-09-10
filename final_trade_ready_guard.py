"""ATLAS final fail-closed 4-12H TRADE READY guard.

Installed after every Production decision overlay. By default it never promotes WAIT,
changes scores/thresholds, or routes orders. It only certifies an already-actionable
LONG/SHORT when HTF direction, entry confirmation, canonical geometry and raw
Production qualification all agree. Any contradiction is collapsed to WAIT
across user-facing/nested plan fields so no stale actionable flag can escape.

An explicitly isolated evidence cohort may opt in to testing whether a stale legacy
pre-final WAIT is redundant when every authoritative final condition already passes.
That experiment is disabled by default and cannot change the Production threshold.
"""
from __future__ import annotations

import os

from canonical_decision_contract import from_decision
from golden_thesis_engine import VERSION as GOLDEN_THESIS_VERSION, build as build_golden_thesis

VERSION = "FINAL_TRADE_READY_GUARD_V3_EXPERIMENTAL_GEOMETRY_RESTORE"
PRODUCT_HORIZON = "4-12H"
EXPERIMENTAL_PROMOTION_ENV = "ATLAS_EXPERIMENTAL_FINAL_EVIDENCE_PROMOTION"


def _norm(v):
    return str(v or "").strip().upper()


def _experimental_final_evidence_promotion():
    return str(os.environ.get(EXPERIMENTAL_PROMOTION_ENV, "")).strip().lower() in {"1", "true", "yes", "on"}


def _direction_state(row):
    thesis = row.get("htf_thesis") or {}
    product = _norm(row.get("product_direction") or thesis.get("product_direction") or thesis.get("direction"))
    entry = _norm(row.get("entry_confirmation_direction") or thesis.get("entry_confirmation_direction") or row.get("candidate_direction"))
    alignment = _norm(row.get("direction_alignment") or thesis.get("direction_alignment"))
    candidate = _norm(row.get("candidate_direction"))
    return product, entry, alignment, candidate


def _geometry_ready(row):
    htf = row.get("htf_core_geometry") or {}
    if htf:
        return bool(htf.get("ready")), _norm(htf.get("reason") or ("HTF_GEOMETRY_READY" if htf.get("ready") else "HTF_GEOMETRY_NOT_READY"))
    analyst = row.get("analyst_output") or {}
    canonical = analyst.get("geometry_readiness") or {}
    if canonical:
        return bool(canonical.get("ready")), _norm(canonical.get("reason") or "CANONICAL_GEOMETRY_NOT_READY")
    legacy = row.get("geometry_gate") or {}
    return bool(legacy.get("qualified")), _norm(legacy.get("reason") or "GEOMETRY_NOT_READY")


def _candidate_plan_geometry(row, direction):
    """Return a complete, directionally valid candidate plan or a fail-closed reason."""
    analyst = row.get("analyst_output") or {}
    plan = analyst.get("candidate_plan") or {}
    if not isinstance(plan, dict):
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INCOMPLETE"
    try:
        entry = float(plan.get("entry"))
        stop = float(plan.get("stop_loss"))
        target = float(plan.get("take_profit"))
    except (TypeError, ValueError):
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INCOMPLETE"
    risk = abs(entry - stop)
    if risk <= 0:
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INVALID_GEOMETRY"
    if direction == "LONG" and not (stop < entry < target):
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INVALID_GEOMETRY"
    if direction == "SHORT" and not (target < entry < stop):
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INVALID_GEOMETRY"
    rr = plan.get("risk_reward")
    try:
        rr = float(rr) if rr is not None else abs(target - entry) / risk
    except (TypeError, ValueError):
        rr = abs(target - entry) / risk
    if rr <= 0:
        return None, "EXPERIMENTAL_CANDIDATE_PLAN_INVALID_GEOMETRY"
    return {
        "entry": entry,
        "stop_loss": stop,
        "take_profit": target,
        "tp1": plan.get("tp1"),
        "risk_reward": rr,
        "geometry_provenance": plan.get("geometry_provenance") or {},
    }, None


def assess(row):
    product, entry, alignment, candidate = _direction_state(row)
    action = _norm(row.get("actionable_decision"))
    qualified = row.get("production_signal_qualified") is True
    geometry_ready, geometry_reason = _geometry_ready(row)
    quality_blocked = _norm((row.get("setup_quality_gate") or {}).get("status")) == "BLOCK"
    degraded = bool(row.get("data_degraded", False))
    experimental_promotion = _experimental_final_evidence_promotion()
    blockers = []
    if product not in {"LONG", "SHORT"}: blockers.append("HTF_PRODUCT_DIRECTION_UNRESOLVED")
    if alignment != "ALIGNED": blockers.append("HTF_4H_12H_NOT_ALIGNED")
    if product in {"LONG", "SHORT"} and entry != product: blockers.append("ENTRY_CONFIRMATION_NOT_ALIGNED")
    if product in {"LONG", "SHORT"} and candidate != product: blockers.append("SCORE_DIRECTION_NOT_HTF_DIRECTION")
    if action in {"LONG", "SHORT"}:
        if product in {"LONG", "SHORT"} and action != product: blockers.append("ACTION_NOT_HTF_DIRECTION")
    elif not experimental_promotion:
        blockers.append("PRE_FINAL_DECISION_NOT_ACTIONABLE")
    if not qualified: blockers.append("PRODUCTION_SIGNAL_NOT_QUALIFIED")
    if not geometry_ready: blockers.append(geometry_reason or "CANONICAL_GEOMETRY_NOT_READY")
    if quality_blocked: blockers.append("SETUP_QUALITY_GATE_BLOCKED")
    if degraded: blockers.append("DATA_DEGRADED")
    candidate_geometry = None
    stale_wait_candidate = bool(experimental_promotion and action not in {"LONG", "SHORT"})
    if stale_wait_candidate and not blockers and product in {"LONG", "SHORT"}:
        candidate_geometry, candidate_geometry_error = _candidate_plan_geometry(row, product)
        if candidate_geometry_error:
            blockers.append(candidate_geometry_error)
    blockers = list(dict.fromkeys(x for x in blockers if x))
    ready = not blockers
    stale_wait_bypassed = bool(stale_wait_candidate and ready)
    return {
        "version": VERSION,
        "status": "TRADE_READY" if ready else "WAIT",
        "trade_ready": ready,
        "direction": product if ready else None,
        "product_direction": product if product in {"LONG", "SHORT"} else None,
        "entry_confirmation_direction": entry if entry in {"LONG", "SHORT"} else None,
        "candidate_direction": candidate if candidate in {"LONG", "SHORT"} else None,
        "pre_final_action": action if action in {"LONG", "SHORT"} else "WAIT",
        "direction_alignment": alignment or None,
        "production_signal_qualified": qualified,
        "canonical_geometry_ready": geometry_ready,
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else None,
        "authority": "FINAL_12H_4H_DIRECTION_PLUS_1H_CONFIRMATION",
        "product_horizon": PRODUCT_HORIZON,
        "score_changed": False,
        "threshold_changed": False,
        "experimental_final_evidence_promotion": experimental_promotion,
        "stale_pre_final_wait_bypassed": stale_wait_bypassed,
        "experimental_candidate_geometry_restored": bool(stale_wait_bypassed and candidate_geometry),
        "candidate_geometry": candidate_geometry if stale_wait_bypassed else None,
        "can_promote_wait": experimental_promotion,
        "paper_trade_eligible": ready,
        "analysis_only": True,
        "live_execution": False,
    }


def _collapse_plan(plan, reason):
    if not isinstance(plan, dict):
        return plan
    out = dict(plan)
    out.update({"status":"WAIT","action":"WAIT","analysis_action":"WAIT","analysis_ready":False,"can_execute":False,"trade_ready":False,"final_trade_ready_reason":reason})
    core = out.get("core_plan")
    if isinstance(core, dict):
        core = dict(core)
        core.update({"status":"WAIT","action":"WAIT","analysis_action":"WAIT","analysis_ready":False,"can_execute":False,"trade_ready":False,"final_trade_ready_reason":reason})
        out["core_plan"] = core
    return out


def _publish_truth(row):
    canonical = from_decision(row, symbol=row.get("symbol"), captured_at=row.get("captured_at") or row.get("generated_at"))
    row["canonical_decision"] = canonical
    row["canonical_wait_reason"] = canonical.get("wait_reason")
    row["canonical_decision_id"] = canonical.get("decision_id")
    analyst = row.get("analyst_output")
    if isinstance(analyst, dict):
        analyst = dict(analyst)
        analyst["canonical_decision_id"] = canonical.get("decision_id")
        analyst["decision_source_of_truth"] = canonical.get("source_of_truth")
        analyst["canonical_decision_schema"] = canonical.get("schema")
        analyst["evaluation_horizons_h"] = list(canonical.get("evaluation_horizons_h") or [])
        analyst["product_horizon"] = canonical.get("product_horizon")
        analyst["geometry_bound_to_canonical_decision"] = bool(canonical.get("decision_id"))
        golden = build_golden_thesis(row, analyst)
        golden["canonical_decision_id"] = canonical.get("decision_id")
        golden["bound_after_final_trade_gate"] = True
        analyst["golden_thesis"] = golden
        row["analyst_output"] = analyst
        row["golden_thesis"] = golden
    return row


def apply(row):
    if not isinstance(row, dict) or not row.get("ok"):
        return row
    gate = assess(row)
    row["final_trade_gate"] = gate
    row["final_trade_gate_version"] = VERSION
    row["trade_ready"] = bool(gate["trade_ready"])
    row["paper_trade_eligible"] = bool(gate["trade_ready"])
    row["analysis_only"] = True
    row["live_execution"] = False
    if gate["trade_ready"]:
        row["canonical_product_decision"] = gate["direction"]
        analyst = row.get("analyst_output")
        if isinstance(analyst, dict):
            analyst = dict(analyst)
            analyst["trade_ready"] = True
            analyst["final_trade_gate"] = gate
            analyst["analysis_ready"] = True
            analyst["decision"] = gate["direction"]
            if gate.get("stale_pre_final_wait_bypassed"):
                restored = gate.get("candidate_geometry") or {}
                analyst.update({
                    "entry": restored.get("entry"),
                    "stop_loss": restored.get("stop_loss"),
                    "take_profit": restored.get("take_profit"),
                    "tp1": restored.get("tp1"),
                    "risk_reward": restored.get("risk_reward"),
                    "geometry_provenance": restored.get("geometry_provenance") or {},
                })
            row["analyst_output"] = analyst
        plan = row.get("trade_plan")
        if isinstance(plan, dict):
            plan = dict(plan); plan["trade_ready"] = True
            core = plan.get("core_plan")
            if isinstance(core, dict):
                core = dict(core); core["trade_ready"] = True; plan["core_plan"] = core
            row["trade_plan"] = plan
        return _publish_truth(row)

    reason = gate["primary_blocker"] or "FINAL_TRADE_GATE_BLOCKED"
    row["pre_final_trade_gate_actionable_decision"] = row.get("actionable_decision")
    row["actionable_decision"] = "WAIT"
    row["actionable_reason"] = reason
    row["wait_reason"] = reason
    row["analysis_ready"] = False
    row["setup_ready"] = False
    row["can_execute"] = False
    row["canonical_product_decision"] = "WAIT"
    row["trade_plan"] = _collapse_plan(row.get("trade_plan"), reason)

    primary = row.get("primary_analysis")
    if isinstance(primary, dict):
        primary = dict(primary); primary.update({"decision":"WAIT","analysis_ready":False,"setup_ready":False,"trade_ready":False,"reason":reason}); row["primary_analysis"] = primary
    matrix = row.get("timeframe_matrix")
    if isinstance(matrix, dict):
        matrix = dict(matrix); core = matrix.get("core_4_12h")
        if isinstance(core, dict):
            core = dict(core); core.update({"decision":"WAIT","analysis_ready":False,"setup_ready":False,"trade_ready":False,"reason":reason}); matrix["core_4_12h"] = core
        row["timeframe_matrix"] = matrix
    best = row.get("best_available_action")
    if isinstance(best, dict):
        best = dict(best); best.update({"action":"WAIT","status":"FINAL_TRADE_GATE_BLOCKED","can_execute":False,"trade_ready":False,"reason":reason}); row["best_available_action"] = best
    analyst = row.get("analyst_output")
    if isinstance(analyst, dict):
        analyst = dict(analyst)
        analyst.update({"decision":"WAIT","analysis_ready":False,"trade_ready":False,"entry":None,"stop_loss":None,"take_profit":None,"tp1":None,"risk_reward":None,"primary_reason":reason,"final_trade_gate":gate})
        reasons = list(analyst.get("reasons") or [])
        if reason not in reasons: reasons.insert(0, reason)
        analyst["reasons"] = reasons
        row["analyst_output"] = analyst
    return _publish_truth(row)


def install(atlas):
    original = atlas.production_decision
    def guarded(symbol):
        row = original(symbol)
        if isinstance(row, dict):
            row = dict(row)
            row.setdefault("symbol", symbol)
        return apply(row)
    atlas.production_decision = guarded
    state = {
        "enabled":True,"version":VERSION,"product_horizon":PRODUCT_HORIZON,
        "fail_closed":True,"paper_portfolio_authority":"final_trade_gate",
        "canonical_decision_contract":"ATLAS_CANONICAL_DECISION_TRUTH_V1",
        "golden_thesis_version":GOLDEN_THESIS_VERSION,"golden_thesis_shadow_only":True,
        "golden_thesis_can_override":False,"analysis_only":True,"live_execution":False,
        "experimental_final_evidence_promotion_env":EXPERIMENTAL_PROMOTION_ENV,
        "experimental_final_evidence_promotion_default":False,
    }
    atlas.FINAL_TRADE_READY_GUARD_STATE = state
    return state
