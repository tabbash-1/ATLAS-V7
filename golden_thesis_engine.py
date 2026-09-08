"""ATLAS Golden Thesis Engine V1.

Deterministic, shadow-only thesis/falsification layer for the canonical 4-12H
analyst product. It does not change Production score, threshold, geometry, or
LONG/SHORT/WAIT. Promotion requires chronological holdout + prospective proof.
"""
from __future__ import annotations

VERSION = "ATLAS_GOLDEN_THESIS_ENGINE_V1_SHADOW"


def _norm(v):
    return str(v or "").strip().upper()


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def build(row, analyst_output):
    row = row or {}
    out = analyst_output or {}
    ds = out.get("direction_state") or {}
    geo = out.get("geometry_readiness") or {}
    profile = out.get("evidence_profile") or {}
    gate = out.get("setup_quality_gate") or {}

    product = _norm(out.get("product_direction") or ds.get("product_direction"))
    entry = _norm(out.get("entry_confirmation_direction") or ds.get("entry_confirmation_direction"))
    alignment = _norm(out.get("direction_alignment") or ds.get("alignment"))
    decision = _norm(out.get("decision"))
    candidate = _norm((out.get("candidate_plan") or {}).get("direction") or row.get("candidate_direction"))

    score = _num(out.get("confidence"))
    threshold = _num(out.get("signal_threshold"))
    margin = score - threshold if score is not None and threshold is not None else None
    rr = _num(out.get("risk_reward"))
    if rr is None:
        rr = _num((out.get("candidate_plan") or {}).get("risk_reward"))

    supporting = []
    opposing = []
    fatal = []

    if product in ("LONG", "SHORT"):
        supporting.append("HTF_12H_4H_DIRECTION_PRESENT")
    else:
        fatal.append("NO_HTF_PRODUCT_DIRECTION")

    if alignment == "ALIGNED" and entry == product and product in ("LONG", "SHORT"):
        supporting.append("ONE_HOUR_ENTRY_CONFIRMATION_ALIGNED")
    else:
        opposing.append("ONE_HOUR_NOT_ALIGNED_WITH_HTF")

    if geo.get("ready") is True:
        supporting.append("CANONICAL_GEOMETRY_READY")
    else:
        fatal.append("CANONICAL_GEOMETRY_NOT_READY")

    if gate.get("status") == "BLOCK":
        fatal.append(_norm(gate.get("reason")) or "SETUP_QUALITY_BLOCK")

    if out.get("data_degraded") or row.get("data_degraded"):
        fatal.append("DATA_DEGRADED")

    for c in profile.get("confirmations") or []:
        code = _norm(c)
        if code:
            supporting.append(code)
    for w in profile.get("warnings") or []:
        code = _norm(w.get("code")) or "UNSPECIFIED_WARNING"
        opposing.append(code)

    if margin is not None:
        if margin >= 0:
            supporting.append("PRODUCTION_SCORE_CLEARS_THRESHOLD")
        else:
            opposing.append("PRODUCTION_SCORE_BELOW_THRESHOLD")

    # Counterfactual: explicitly state the strongest case against the thesis.
    if fatal:
        strongest_countercase = fatal[0]
    elif opposing:
        strongest_countercase = opposing[0]
    else:
        strongest_countercase = "NO_MATERIAL_COUNTERCASE_DETECTED_FROM_VALIDATED_INPUTS"

    thesis_valid = (
        product in ("LONG", "SHORT")
        and alignment == "ALIGNED"
        and entry == product
        and geo.get("ready") is True
        and not fatal
    )
    trigger_ready = decision in ("LONG", "SHORT") and out.get("analysis_ready") is True

    if thesis_valid and trigger_ready:
        stage = "TRADE_READY"
    elif thesis_valid:
        stage = "THESIS_VALID_WAIT_TRIGGER"
    elif product in ("LONG", "SHORT"):
        stage = "THESIS_FORMING"
    else:
        stage = "NO_THESIS"

    # In shadow V1 the canonical decision is the immutable truth.
    contradiction = None
    if decision in ("LONG", "SHORT") and decision != product:
        contradiction = "CANONICAL_ACTION_CONTRADICTS_HTF_PRODUCT_DIRECTION"
    if decision in ("LONG", "SHORT") and not thesis_valid:
        contradiction = contradiction or "CANONICAL_ACTION_WITHOUT_COMPLETE_GOLDEN_THESIS"

    return {
        "version": VERSION,
        "mode": "SHADOW_FALSIFICATION_ONLY",
        "horizon": "4-12H",
        "stage": stage,
        "thesis_direction": product if product in ("LONG", "SHORT") else "NONE",
        "canonical_decision": decision if decision in ("LONG", "SHORT", "WAIT") else "WAIT",
        "candidate_direction": candidate if candidate in ("LONG", "SHORT") else "NONE",
        "thesis_valid": thesis_valid,
        "entry_trigger_ready": trigger_ready,
        "supporting_evidence": list(dict.fromkeys(supporting)),
        "opposing_evidence": list(dict.fromkeys(opposing)),
        "fatal_invalidations": list(dict.fromkeys(fatal)),
        "strongest_countercase": strongest_countercase,
        "score_margin": round(margin, 2) if margin is not None else None,
        "candidate_rr": round(rr, 3) if rr is not None else None,
        "contradiction": contradiction,
        "promotion_status": "SHADOW_ONLY_REQUIRES_CHRONOLOGICAL_HOLDOUT_AND_PROSPECTIVE_VALIDATION",
        "can_override_canonical_decision": False,
        "can_change_score": False,
        "can_change_threshold": False,
        "can_change_geometry": False,
        "analysis_only": True,
        "live_execution": False,
    }
