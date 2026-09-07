"""ATLAS final fail-closed 4-12H TRADE READY guard.

Installed after every Production decision overlay. It never promotes WAIT, changes
scores/thresholds, or routes orders. It only certifies an already-actionable
LONG/SHORT when HTF direction, entry confirmation, canonical geometry and raw
Production qualification all agree. Any contradiction is collapsed to WAIT
across user-facing/nested plan fields so no stale actionable flag can escape.
"""
from __future__ import annotations

VERSION = "FINAL_TRADE_READY_GUARD_V1_HTF_FAIL_CLOSED"
PRODUCT_HORIZON = "4-12H"


def _norm(v):
    return str(v or "").strip().upper()


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


def assess(row):
    product, entry, alignment, candidate = _direction_state(row)
    action = _norm(row.get("actionable_decision"))
    qualified = row.get("production_signal_qualified") is True
    geometry_ready, geometry_reason = _geometry_ready(row)
    quality_blocked = _norm((row.get("setup_quality_gate") or {}).get("status")) == "BLOCK"
    degraded = bool(row.get("data_degraded", False))
    blockers = []
    if product not in {"LONG", "SHORT"}: blockers.append("HTF_PRODUCT_DIRECTION_UNRESOLVED")
    if alignment != "ALIGNED": blockers.append("HTF_4H_12H_NOT_ALIGNED")
    if product in {"LONG", "SHORT"} and entry != product: blockers.append("ENTRY_CONFIRMATION_NOT_ALIGNED")
    if product in {"LONG", "SHORT"} and candidate != product: blockers.append("SCORE_DIRECTION_NOT_HTF_DIRECTION")
    if action not in {"LONG", "SHORT"}: blockers.append("PRE_FINAL_DECISION_NOT_ACTIONABLE")
    elif product in {"LONG", "SHORT"} and action != product: blockers.append("ACTION_NOT_HTF_DIRECTION")
    if not qualified: blockers.append("PRODUCTION_SIGNAL_NOT_QUALIFIED")
    if not geometry_ready: blockers.append(geometry_reason or "CANONICAL_GEOMETRY_NOT_READY")
    if quality_blocked: blockers.append("SETUP_QUALITY_GATE_BLOCKED")
    if degraded: blockers.append("DATA_DEGRADED")
    # Preserve order while removing duplicates.
    blockers = list(dict.fromkeys(x for x in blockers if x))
    ready = not blockers
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
        "can_promote_wait": False,
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
        # Certification only: never promote or relabel the pre-final decision.
        row["canonical_product_decision"] = gate["direction"]
        analyst = row.get("analyst_output")
        if isinstance(analyst, dict):
            analyst = dict(analyst)
            analyst["trade_ready"] = True
            analyst["final_trade_gate"] = gate
            analyst["analysis_ready"] = True
            row["analyst_output"] = analyst
        plan = row.get("trade_plan")
        if isinstance(plan, dict):
            plan = dict(plan); plan["trade_ready"] = True
            core = plan.get("core_plan")
            if isinstance(core, dict):
                core = dict(core); core["trade_ready"] = True; plan["core_plan"] = core
            row["trade_plan"] = plan
        return row

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
    return row


def install(atlas):
    original = atlas.production_decision
    def guarded(symbol):
        return apply(original(symbol))
    atlas.production_decision = guarded
    state = {"enabled":True,"version":VERSION,"product_horizon":PRODUCT_HORIZON,"fail_closed":True,"paper_portfolio_authority":"trade_ready","analysis_only":True,"live_execution":False}
    atlas.FINAL_TRADE_READY_GUARD_STATE = state
    return state
