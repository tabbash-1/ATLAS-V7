"""ATLAS final fail-closed 4-12H TRADE READY guard.

Installed after every Production decision overlay. It never changes scores/thresholds
or routes orders. It certifies LONG/SHORT only when HTF direction, entry confirmation,
canonical geometry, raw Production qualification and Trader Brain evidence all agree.
Breakout-family setups additionally require explicit canonical structure-break
confirmation. Any contradiction is collapsed to WAIT across user-facing/nested plan
fields so no stale actionable flag can escape.

Evidence-gated SHORT certification and removal of a stale pre-final WAIT veto are on by
default. Both retain explicit kill switches, never lower the Production threshold, and
cannot bypass any authoritative Final Gate blocker.
"""
from __future__ import annotations

import os

from atlas_trader_brain import assess as assess_trader
from canonical_decision_contract import from_decision
from golden_thesis_engine import VERSION as GOLDEN_THESIS_VERSION, build as build_golden_thesis

VERSION = "FINAL_TRADE_READY_GUARD_V13_ANALYST_AUTHORITY"
MIN_NET_RR = 2.0
SHORT_PRODUCTION_ENV = "ATLAS_SHORT_PRODUCTION_ENABLED"
PRODUCT_HORIZON = "4-12H"
EXPERIMENTAL_PROMOTION_ENV = "ATLAS_EXPERIMENTAL_FINAL_EVIDENCE_PROMOTION"


def _norm(v):
    return str(v or "").strip().upper()


def _short_production_enabled():
    """Allow evidence-complete SHORT analysis unless an explicit kill switch disables it."""
    raw = os.environ.get(SHORT_PRODUCTION_ENV)
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _experimental_final_evidence_promotion():
    """Remove only a stale pre-final WAIT veto after every Final Gate check passes."""
    raw = os.environ.get(EXPERIMENTAL_PROMOTION_ENV)
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _direction_state(row):
    thesis = row.get("htf_thesis") or {}
    product = _norm(row.get("product_direction") or thesis.get("product_direction") or thesis.get("direction"))
    entry = _norm(row.get("entry_confirmation_direction") or thesis.get("entry_confirmation_direction") or row.get("candidate_direction"))
    alignment = _norm(row.get("direction_alignment") or thesis.get("direction_alignment"))
    candidate = _norm(row.get("candidate_direction"))
    return product, entry, alignment, candidate


def _authoritative_context_state(row):
    """Final read of top-down analyst authority before TRADE_READY.

    Earlier overlays may preserve a candidate direction for diagnostics even when the
    canonical HTF thesis has already said WAIT (for example: macro opposition or an
    entry into HTF resistance/support).  Final Gate must never re-promote those rows.
    BTC-first is also rechecked here so later geometry/quality overlays cannot bypass
    the market-anchor decision for altcoins.
    """
    thesis = row.get("htf_thesis") or {}
    thesis_status = _norm(thesis.get("status"))
    thesis_reason = _norm(thesis.get("reason"))

    symbol = _norm(row.get("symbol")).replace("BINANCE:", "")
    btc_gate = row.get("market_direction_gate") or {}
    btc_gate_present = isinstance(btc_gate, dict) and bool(btc_gate)
    btc_pass = btc_gate.get("pass") is True if btc_gate_present else None
    btc_reason = _norm(btc_gate.get("reason")) if btc_gate_present else None

    blockers = []
    # Explicit canonical HTF WAIT/BLOCK is authoritative. Missing status remains
    # backward-compatible for isolated fixtures/legacy evidence, but live Production
    # always publishes the HTF thesis status before Final Gate.
    if thesis_status in {"WAIT", "BLOCK"}:
        blockers.append("HTF_THESIS_" + (thesis_reason or "NOT_PASS"))

    if symbol and symbol != "BTCUSDT" and btc_gate_present and not btc_pass:
        blockers.append("BTC_FIRST_" + (btc_reason or "GATE_NOT_CONFIRMED"))

    return {
        "htf_thesis_status": thesis_status or None,
        "htf_thesis_reason": thesis_reason or None,
        "btc_first_gate_present": btc_gate_present,
        "btc_first_pass": btc_pass,
        "btc_first_reason": btc_reason,
        "blockers": blockers,
        "rule": "EXPLICIT_HTF_WAIT_OR_BLOCK_AND_EXPLICIT_BTC_FIRST_FAILURE_CANNOT_BE_PROMOTED",
    }


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


def _breakout_structure_state(row):
    """Return whether this setup requires breakout confirmation and its evidence.

    The guard intentionally scopes the new rule to breakout-family setups only. Other
    valid setup families (for example trend pullbacks) keep their existing gate path.
    Confirmation is accepted only from canonical structure/plan fields; playbook names
    can declare the requirement but can never manufacture confirmation evidence.
    """
    analyst = row.get("analyst_output") or {}
    trade_plan = row.get("trade_plan") or {}
    core_plan = trade_plan.get("core_plan") or {}
    structural = row.get("structural_geometry") or {}
    breakout = structural.get("breakout") or {}
    provenance = trade_plan.get("geometry_provenance") or core_plan.get("geometry_provenance") or {}

    playbook = _norm(
        row.get("playbook")
        or row.get("playbook_primary")
        or analyst.get("playbook")
        or analyst.get("playbook_primary")
    )
    entry_mode = _norm(trade_plan.get("entry_mode") or core_plan.get("entry_mode"))
    requires_confirmation = bool("BREAKOUT" in playbook or entry_mode == "BREAKOUT")

    evidence_present = False
    confirmed = False
    evidence_source = None
    candidates = (
        ("STRUCTURAL_GEOMETRY", breakout, "confirmed"),
        ("TRADE_PLAN", trade_plan, "breakout_confirmed"),
        ("CORE_PLAN", core_plan, "breakout_confirmed"),
        ("GEOMETRY_PROVENANCE", provenance, "breakout_confirmed"),
    )
    for source, obj, key in candidates:
        if isinstance(obj, dict) and key in obj:
            evidence_present = True
            confirmed = obj.get(key) is True
            evidence_source = source
            break

    return {
        "requires_confirmation": requires_confirmation,
        "confirmed": confirmed,
        "evidence_present": evidence_present,
        "evidence_source": evidence_source,
        "playbook": playbook or None,
        "entry_mode": entry_mode or None,
    }


def _net_rr_state(row):
    """Evaluate RR after explicit execution costs when validated cost evidence exists.

    Cost evidence must be validated before a trade can be certified. No fee,
    spread, or slippage values are invented when the live estimate is unavailable.
    """
    plan=row.get("trade_plan") or {}
    entry=plan.get("entry"); stop=plan.get("stop_loss"); gross=plan.get("rr_tp2")
    shadow=row.get("profit_engine_shadow") or {}
    # The live cost estimator is owned by profit_engine_runtime and publishes
    # its validated snapshot under shadow.execution. Accept that canonical
    # source as well as the direct fields used by isolated callers/tests.
    cost=(row.get("execution_cost") or row.get("execution_cost_model")
          or shadow.get("execution_cost") or shadow.get("execution") or {})
    cost_blockers=(row.get("execution_cost_blockers")
                   or shadow.get("execution_cost_blockers")
                   or cost.get("blockers") or [])
    snapshot_attached=bool(cost)
    evidence={
        "cost_snapshot_status": "ATTACHED_VALIDATED" if cost.get("validated") is True else "ATTACHED_UNVALIDATED" if snapshot_attached else "NOT_ATTACHED_TO_PRODUCTION_DECISION",
        "cost_source_version": cost.get("version") or shadow.get("execution_cost_source_version"),
        "cost_basis": cost.get("basis"),
        "cost_blockers": list(cost_blockers),
        "configuration_required": None,
        "report_note": "Execution cost evidence is unavailable; net R:R is not reported." if not snapshot_attached else None,
    }
    try:
        entry=float(entry); stop=float(stop); gross=float(gross)
    except (TypeError, ValueError):
        return {"validated":False,"gross_rr":gross,"net_rr":None,"reason":"NET_RR_GEOMETRY_UNAVAILABLE",**evidence}
    if cost.get("validated") is not True:
        return {"validated":False,"gross_rr":gross,"net_rr":None,"reason":"EXECUTION_COST_EVIDENCE_UNAVAILABLE",**evidence}
    try:
        from execution_cost_model import apply_cost_to_r
        out=apply_cost_to_r(gross,entry=entry,risk_abs=abs(entry-stop),fee_bps=cost.get("fee_bps"),spread_bps=cost.get("spread_bps"),slippage_bps=cost.get("slippage_bps"))
    except Exception as exc:
        return {"validated":False,"gross_rr":gross,"net_rr":None,"reason":"EXECUTION_COST_EVIDENCE_INVALID","error":str(exc),**evidence}
    return {"validated":bool(out and out.get("validated_cost_inputs")),"gross_rr":gross,"net_rr":None if not out else out.get("net_r"),"execution_cost_r":None if not out else out.get("execution_cost_r"),"round_trip_cost_bps":None if not out else out.get("round_trip_cost_bps"),"reason":"NET_RR_VALIDATED" if out and out.get("validated_cost_inputs") else "EXECUTION_COST_EVIDENCE_INVALID",**evidence}

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
    structure_state = _breakout_structure_state(row)
    quality_blocked = _norm((row.get("setup_quality_gate") or {}).get("status")) == "BLOCK"
    degraded = bool(row.get("data_degraded", False))
    experimental_promotion = _experimental_final_evidence_promotion()
    net_rr = _net_rr_state(row)
    authoritative_context = _authoritative_context_state(row)
    alignment_accepted = alignment in {"ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"}
    blockers = list(authoritative_context.get("blockers") or [])
    if product == "SHORT" and not _short_production_enabled(): blockers.append("SHORT_EDGE_NOT_PROVEN_PRODUCTION_QUARANTINE")
    if not qualified: blockers.append("PRODUCTION_SIGNAL_NOT_QUALIFIED")
    if product not in {"LONG", "SHORT"}:
        blockers.append("HTF_PRODUCT_DIRECTION_UNRESOLVED")
        blockers.append("HTF_4H_12H_NOT_ALIGNED")
    elif entry != product:
        # 4H/12H may already agree on the product direction while the separate
        # entry confirmation still opposes it. Do not mislabel that state as an
        # HTF disagreement; the decision remains WAIT under the precise cause.
        blockers.append("ENTRY_CONFIRMATION_NOT_ALIGNED")
    elif not alignment_accepted:
        blockers.append("DIRECTION_ALIGNMENT_NOT_ACCEPTED")
    if action in {"LONG", "SHORT"}:
        if product in {"LONG", "SHORT"} and action != product: blockers.append("ACTION_NOT_HTF_DIRECTION")
    if not geometry_ready: blockers.append(geometry_reason or "CANONICAL_GEOMETRY_NOT_READY")
    if structure_state["requires_confirmation"]:
        if not structure_state["evidence_present"]:
            blockers.append("BREAKOUT_CONFIRMATION_EVIDENCE_MISSING")
        elif not structure_state["confirmed"]:
            blockers.append("BREAKOUT_STRUCTURE_NOT_CONFIRMED")
    if quality_blocked: blockers.append("SETUP_QUALITY_GATE_BLOCKED")
    if degraded: blockers.append("DATA_DEGRADED")
    # ATLAS is an analysis product. Execution costs are reported when evidence
    # exists, but venue configuration and estimated fees must not decide LONG,
    # SHORT, or WAIT. Analytical geometry and structure gates remain in force.
    trader = assess_trader(row)
    for blocker in trader.get("fatal_blockers") or []:
        blockers.append(blocker)
    # Timing/location waits are non-fatal to the thesis, but they must block entry.
    for blocker in trader.get("wait_blockers") or []:
        blockers.append(blocker)
    candidate_geometry = None
    stale_wait_candidate = bool(action not in {"LONG", "SHORT"})
    # A pre-final WAIT must remain WAIT unless the explicit promotion experiment is enabled.
    # Merely having no other blockers is not authority to synthesize TRADE_READY.
    if stale_wait_candidate and not experimental_promotion:
        blockers.append("PRE_FINAL_WAIT_PROMOTION_DISABLED")
    if stale_wait_candidate and experimental_promotion and not blockers and product in {"LONG", "SHORT"}:
        candidate_geometry, candidate_geometry_error = _candidate_plan_geometry(row, product)
        if candidate_geometry_error:
            blockers.append(candidate_geometry_error)
    blockers = list(dict.fromkeys(x for x in blockers if x))
    ready = not blockers
    stale_wait_bypassed = bool(stale_wait_candidate and experimental_promotion and ready)
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
        "score_is_authority": False,
        "production_qualification_required": True,
        "trader_brain": trader,
        "trader_stage": trader.get("stage"),
        "setup_playbook": trader.get("setup_playbook"),
        "location_state": trader.get("location_state"),
        "minimum_rr_required": trader.get("minimum_rr_required"),
        "minimum_net_rr_after_costs": MIN_NET_RR,
        "net_rr_after_costs": net_rr,
        "net_rr_cost_evidence_required_for_claim": True,
        "net_rr_cost_evidence_required_for_trade_ready": False,
        "execution_costs_affect_analysis_decision": False,
        "execution_costs_role": "REPORT_ONLY",
        "canonical_geometry_ready": geometry_ready,
        "structure_confirmation": structure_state,
        "authoritative_context": authoritative_context,
        "htf_thesis_status_required_when_explicit": True,
        "btc_first_rechecked_at_final_gate": True,
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else None,
        "authority": "FINAL_EVIDENCE_4_12H_THESIS_PLUS_1H_TRIGGER_PLUS_STRUCTURE",
        "product_horizon": PRODUCT_HORIZON,
        "score_changed": False,
        "threshold_changed": False,
        "experimental_final_evidence_promotion": experimental_promotion,
        "legacy_pre_final_action_is_authority": False,
        "accepted_alignment_classes": ["ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"],
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
        previous_action = row.get("actionable_decision")
        if gate.get("stale_pre_final_wait_bypassed"):
            row["pre_final_trade_gate_actionable_decision"] = previous_action
        row["actionable_decision"] = gate["direction"]
        row["actionable_reason"] = "FINAL_TRADE_GATE_APPROVED"
        row["analysis_ready"] = True
        row["setup_ready"] = True
        row["can_execute"] = True
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
            plan = dict(plan)
            plan.update({
                "status":"TRADE_READY", "action":gate["direction"],
                "analysis_action":gate["direction"], "analysis_ready":True,
                "can_execute":True, "trade_ready":True,
                "final_trade_ready_reason":"FINAL_TRADE_GATE_APPROVED",
            })
            core = plan.get("core_plan")
            if isinstance(core, dict):
                core = dict(core)
                core.update({
                    "status":"TRADE_READY", "action":gate["direction"],
                    "analysis_action":gate["direction"], "analysis_ready":True,
                    "can_execute":True, "trade_ready":True,
                    "final_trade_ready_reason":"FINAL_TRADE_GATE_APPROVED",
                })
                plan["core_plan"] = core
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
        "breakout_structure_confirmation_required":True,
        "breakout_structure_confirmation_scope":"BREAKOUT_FAMILY_ONLY",
        "experimental_final_evidence_promotion_env":EXPERIMENTAL_PROMOTION_ENV,
        "experimental_final_evidence_promotion_default":True,
        "short_production_env":SHORT_PRODUCTION_ENV,
        "short_production_default":"EVIDENCE_GATED",
        "score_is_authority":False,"trader_brain_authority":True,
        "legacy_pre_final_wait_veto_removed":True,
        "conditional_12h_neutral_alignment_supported":True,
    }
    atlas.FINAL_TRADE_READY_GUARD_STATE = state
    return state
