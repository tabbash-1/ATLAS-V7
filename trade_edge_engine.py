"""ATLAS Trade Edge V1 — separate prediction quality from execution quality.

This module is deliberately shadow/research-only. It does not change Production,
thresholds, FINAL_TRADE_GATE, alerts, or execution. It turns existing ATLAS evidence
into one auditable lifecycle:

regime -> direction -> setup -> entry trigger -> geometry -> expected-value estimate.

The probability estimate is empirical and conservative: it uses the current
independent non-overlapping 12H audit only for setup families with enough evidence.
It is not a machine-learning model and must not be promoted without prospective
out-of-sample validation.
"""
from __future__ import annotations

VERSION = "ATLAS_TRADE_EDGE_V1_SHADOW"
MIN_SAMPLE = 12
MIN_RR = 2.0
PRODUCT_HORIZON = "4-12H"

# Frozen from status/monthly-product-audit-latest.json generated
# 2026-09-23T05:54:39.198476+00:00. These are directional 12H outcomes, not
# claims of realized trade profitability. They are used only as a prior.
FAMILY_PRIORS = {
    ("LONG", "TREND_UP", "MARKET_CONTINUATION_LONG"): {
        "n": 16, "positive_pct": 68.75, "mean_pct": 1.63902,
        "loss_ge_1_pct": 18.75,
    },
    ("LONG", "TREND_UP", "TREND_PULLBACK_LONG"): {
        "n": 14, "positive_pct": 64.29, "mean_pct": -0.15266,
        "loss_ge_1_pct": 28.57,
    },
}


def _norm(v):
    return str(v or "").strip().upper()


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def _family(row):
    thesis = row.get("htf_thesis") or {}
    direction = _norm(row.get("product_direction") or thesis.get("product_direction") or thesis.get("direction") or row.get("candidate_direction"))
    regime = _norm(row.get("regime"))
    playbook = _norm(row.get("playbook"))
    return direction, regime, playbook


def _entry_ready(row, direction):
    thesis = row.get("htf_thesis") or {}
    entry = _norm(row.get("entry_confirmation_direction") or thesis.get("entry_confirmation_direction"))
    alignment = _norm(row.get("direction_alignment") or thesis.get("direction_alignment"))
    return bool(direction in {"LONG", "SHORT"} and entry == direction and alignment in {
        "ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"
    })


def _geometry(row):
    htf = row.get("htf_core_geometry") or {}
    plan = row.get("trade_plan") or {}
    core = plan.get("core_plan") or plan
    rr = _num(htf.get("rr_tp2"))
    if rr is None:
        rr = _num(plan.get("rr_tp2"))
    if rr is None:
        rr = _num(core.get("rr_tp2"))
    ready = bool(htf.get("ready")) if htf else bool(((row.get("analyst_output") or {}).get("geometry_readiness") or {}).get("ready"))
    return ready, rr


def assess(row):
    row = row or {}
    direction, regime, playbook = _family(row)
    prior = FAMILY_PRIORS.get((direction, regime, playbook))
    entry_ready = _entry_ready(row, direction)
    geometry_ready, rr = _geometry(row)
    data_ok = not bool(row.get("data_degraded"))
    sample_ok = bool(prior and prior["n"] >= MIN_SAMPLE)

    # Directional 12H hit-rate is only a prior. It is intentionally shrunk
    # toward 50% so a small historical cohort cannot become false certainty.
    p = None
    if sample_ok:
        n = float(prior["n"])
        wins = n * float(prior["positive_pct"]) / 100.0
        p = (wins + 5.0) / (n + 10.0)  # Beta(5,5) conservative shrinkage.

    # A directional prior cannot authorize a trade. EV is exposed only when
    # the independent entry trigger and canonical geometry are ready.
    ev_r = None
    if p is not None and entry_ready and geometry_ready and rr is not None and rr >= MIN_RR:
        ev_r = p * rr - (1.0 - p)

    if direction not in {"LONG", "SHORT"}:
        stage, reason = "NO_THESIS", "NO_4_12H_DIRECTION"
    elif not sample_ok:
        stage, reason = "RESEARCH_ONLY", "NO_MATURE_SETUP_PRIOR"
    elif not entry_ready:
        stage, reason = "WAIT_TRIGGER", "DIRECTION_PRESENT_ENTRY_NOT_READY"
    elif not geometry_ready or rr is None or rr < MIN_RR:
        stage, reason = "WAIT_GEOMETRY", "ENTRY_PRESENT_GEOMETRY_NOT_READY"
    elif ev_r is None or ev_r <= 0:
        stage, reason = "REJECT_NEGATIVE_EV", "NON_POSITIVE_EMPIRICAL_EV"
    elif not data_ok:
        stage, reason = "REJECT_DATA", "DATA_DEGRADED"
    else:
        stage, reason = "EDGE_CANDIDATE", "POSITIVE_EMPIRICAL_EV_WITH_ENTRY_AND_GEOMETRY"

    return {
        "version": VERSION,
        "product_horizon": PRODUCT_HORIZON,
        "stage": stage,
        "reason": reason,
        "regime": regime or None,
        "direction": direction if direction in {"LONG", "SHORT"} else None,
        "setup": playbook or None,
        "entry_trigger_ready": entry_ready,
        "geometry_ready": geometry_ready,
        "rr_tp2": round(rr, 4) if rr is not None else None,
        "empirical_prior": dict(prior) if prior else None,
        "shrunk_directional_probability": round(p, 4) if p is not None else None,
        "expected_value_r_before_costs": round(ev_r, 4) if ev_r is not None else None,
        "probability_semantics": "SHRUNK_12H_DIRECTIONAL_PRIOR_NOT_TP_BEFORE_SL_PROBABILITY",
        "promotion_requirement": "PROSPECTIVE_TRIPLE_BARRIER_TP_FIRST_VS_SL_FIRST_OUT_OF_SAMPLE_EVIDENCE",
        "can_override_production": False,
        "analysis_only": True,
        "live_execution": False,
    }
