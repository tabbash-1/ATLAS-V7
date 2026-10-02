"""ATLAS Supabase-derived Early Transition V1 — research/shadow only.

Frozen research candidate derived from historical point-in-time opportunity scans.
It is evidence only: it cannot alter Production, Final Gate, thresholds, geometry,
or execution.  The initial validated candidate is deliberately asymmetric:
SHORT only. LONG remains unproven and therefore fails closed.
"""
from __future__ import annotations

VERSION = "ATLAS_SUPABASE_EARLY_TRANSITION_V1"
SOURCE = "SUPABASE_HISTORICAL_RESEARCH"
VALIDATED_HORIZON = "4H"

def _u(v):
    return str(v or "").strip().upper()

def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def assess(observation):
    o = observation or {}
    regime = _u(o.get("regime"))
    btc_1h = _f(o.get("btc_return_1h_pct"))
    mom24 = _f(o.get("price_change_24h_pct"))
    oi = _f(o.get("oi_change_pct"))
    taker = _f(o.get("taker_imbalance"))
    rv = _f(o.get("relative_volume"))

    missing = [
        name for name, value in (
            ("BTC_1H", btc_1h), ("MOMENTUM_24H", mom24),
            ("OI_CHANGE", oi), ("TAKER_IMBALANCE", taker),
            ("RELATIVE_VOLUME", rv),
        ) if value is None
    ]
    if missing:
        return _result(False, "WAIT", [], ["MISSING_" + x for x in missing], None, regime)

    score = (
        (1 if mom24 > 0 else -1)
        + (1 if oi > 0 else -1)
        + (1 if taker > 0 else -1)
        + (1 if rv >= 1 else 0)
        + (1 if btc_1h > 0 else -1)
    )
    btc_state = "BTC_UP" if btc_1h > 0.25 else ("BTC_DOWN" if btc_1h < -0.25 else "BTC_FLAT")

    # Frozen candidate supported across five chronological folds:
    # score <= -3 AND (NEUTRAL+BTC_DOWN OR DOWNTREND_CONTINUATION+BTC_FLAT).
    short_pattern = score <= -3 and (
        (regime == "NEUTRAL" and btc_state == "BTC_DOWN")
        or (regime == "DOWNTREND_CONTINUATION" and btc_state == "BTC_FLAT")
    )
    if not short_pattern:
        return _result(False, "WAIT", [], ["NO_VALIDATED_EARLY_TRANSITION_PATTERN"], score, regime, btc_state)

    evidence = ["NEGATIVE_TRANSITION_SCORE", regime, btc_state]
    return _result(True, "SHORT", evidence, [], score, regime, btc_state)

def _result(eligible, direction, evidence, blockers, score, regime, btc_state=None):
    return {
        "version": VERSION,
        "source": SOURCE,
        "mode": "RESEARCH_SHADOW",
        "validated_horizon": VALIDATED_HORIZON,
        "eligible": bool(eligible),
        "direction": direction,
        "evidence": evidence,
        "blockers": blockers,
        "transition_score": score,
        "regime": regime,
        "btc_state": btc_state,
        "research_only": True,
        "paper_only": True,
        "can_override_production": False,
        "can_override_final_gate": False,
        "can_change_threshold": False,
        "can_change_score": False,
        "can_change_geometry": False,
        "live_execution": False,
    }
