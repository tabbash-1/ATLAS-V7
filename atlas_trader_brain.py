"""ATLAS Trader Brain V1 — one 4-12H trading lifecycle.

This is the decision-quality layer between market analysis and FINAL_TRADE_GATE.
It does not route orders. It converts existing ATLAS evidence into a trader-like
state: thesis -> location -> setup -> trigger -> geometry -> trade/wait.
Legacy score is evidence only and cannot independently authorize or veto a trade.
"""
from __future__ import annotations

VERSION = "ATLAS_TRADER_BRAIN_V1"
MIN_RR = 2.0
ACCEPTED_ALIGNMENT = {"ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"}


def _norm(v):
    return str(v or "").strip().upper()


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _plan(row):
    p = row.get("trade_plan") or {}
    c = p.get("core_plan") or {}
    return c if isinstance(c, dict) and c else p


def _rr2(row):
    p = _plan(row)
    rr = _num(p.get("rr_tp2"))
    if rr is not None:
        return rr
    a = row.get("analyst_output") or {}
    rr = _num(a.get("risk_reward"))
    if rr is not None:
        return rr
    cp = a.get("candidate_plan") or {}
    return _num(cp.get("risk_reward"))


def _playbook(row):
    a = row.get("analyst_output") or {}
    p = _plan(row)
    raw = _norm(row.get("playbook") or row.get("playbook_primary") or a.get("playbook") or a.get("playbook_primary"))
    mode = _norm(p.get("entry_mode"))
    if "SWEEP" in raw or "REVERS" in raw:
        return "LIQUIDITY_SWEEP_REVERSAL"
    if "BREAKOUT" in raw or mode == "BREAKOUT":
        return "BREAKOUT_RETEST"
    if "PULLBACK" in raw or mode == "PULLBACK":
        return "TREND_PULLBACK"
    return "STRUCTURAL_CONTINUATION"


def assess(row):
    row = row or {}
    thesis = row.get("htf_thesis") or {}
    product = _norm(row.get("product_direction") or thesis.get("product_direction") or thesis.get("direction"))
    entry = _norm(row.get("entry_confirmation_direction") or thesis.get("entry_confirmation_direction"))
    alignment = _norm(row.get("direction_alignment") or thesis.get("direction_alignment"))
    geometry = row.get("htf_core_geometry") or {}
    if geometry:
        geometry_ready = geometry.get("ready") is True
    else:
        geometry_ready = ((row.get("analyst_output") or {}).get("geometry_readiness") or {}).get("ready") is True
    quality = row.get("setup_quality_gate") or {}
    quality_blocked = _norm(quality.get("status")) == "BLOCK"
    degraded = bool(row.get("data_degraded"))
    plan = _plan(row)
    mode = _norm(plan.get("entry_mode"))
    rr = _rr2(row)
    playbook = _playbook(row)

    fatal = []
    waits = []
    if product not in {"LONG", "SHORT"}:
        fatal.append("TRADER_NO_DIRECTIONAL_THESIS")
    if alignment not in ACCEPTED_ALIGNMENT:
        fatal.append("TRADER_HTF_CONFLICT")
    if degraded:
        fatal.append("DATA_DEGRADED")
    if quality_blocked:
        fatal.append("SETUP_QUALITY_GATE_BLOCKED")
    if rr is None or rr < MIN_RR:
        fatal.append("TRADER_RR_BELOW_2R")

    if entry != product and product in {"LONG", "SHORT"}:
        waits.append("TRADER_WAIT_1H_TRIGGER")
    if not geometry_ready:
        waits.append("TRADER_WAIT_VALID_LOCATION")

    overextended = any(
        token in _norm(quality.get("reason") or row.get("wait_reason") or row.get("actionable_reason"))
        for token in ("OVEREXTEND", "CHASE", "LATE_ENTRY")
    )
    if overextended:
        waits.append("TRADER_NO_CHASE")

    if fatal:
        stage = "NO_TRADE"
    elif waits:
        stage = "WAIT_TRIGGER" if "TRADER_WAIT_1H_TRIGGER" in waits else "WAIT_LOCATION"
    else:
        stage = "TRADE_READY"

    return {
        "version": VERSION,
        "horizon": "4-12H",
        "stage": stage,
        "directional_thesis": product if product in {"LONG", "SHORT"} else None,
        "alignment_class": alignment or None,
        "location_state": "OVEREXTENDED" if overextended else ("VALID" if geometry_ready else "WAIT"),
        "setup_playbook": playbook,
        "entry_trigger_ready": entry == product and product in {"LONG", "SHORT"},
        "entry_mode": mode or None,
        "geometry_ready": geometry_ready,
        "rr_tp2": round(rr, 3) if rr is not None else None,
        "minimum_rr_required": MIN_RR,
        "fatal_blockers": list(dict.fromkeys(fatal + waits)),
        "legacy_score": _num(row.get("score") or (row.get("analyst_output") or {}).get("confidence")),
        "score_is_authority": False,
        "decision_rule": "THESIS_LOCATION_SETUP_TRIGGER_GEOMETRY",
        "analysis_only": True,
        "live_execution": False,
    }
