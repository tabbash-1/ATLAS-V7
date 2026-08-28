"""Prospective research-only shadow for exact 2-2 directional consensus ties.

Historical audit found the *predeclared* 24h-momentum side stable-positive at
1h and 3h across chronological holdout and leave-one-symbol-out checks. This
module freezes that exact rule prospectively. It never changes Production,
threshold 68, actionable_decision, or execution.
"""
from __future__ import annotations

VERSION = "CONSENSUS_TIEBREAK_SHADOW_V1_MOMENTUM_1H_3H"
HORIZONS_HOURS = (1, 3)


def fnum(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def build_shadow_from_decision(decision):
    d = decision if isinstance(decision, dict) else {}
    symbol = d.get("symbol")
    threshold = fnum(d.get("signal_threshold"), 68.0)
    base = {
        "ok": bool(d.get("ok")),
        "source": VERSION,
        "symbol": symbol,
        "status": "INACTIVE",
        "direction": None,
        "horizons_hours": list(HORIZONS_HOURS),
        "reference_price": fnum(d.get("entry")),
        "production_decision": d.get("decision"),
        "production_actionable_decision": d.get("actionable_decision"),
        "production_wait_reason": d.get("wait_reason"),
        "production_score": fnum(d.get("score")),
        "production_threshold": threshold,
        "direction_votes_long": d.get("direction_votes_long"),
        "direction_votes_short": d.get("direction_votes_short"),
        "momentum_24h_pct": fnum((d.get("indicators") or {}).get("momentum_24h_pct")),
        "generated_at": d.get("generated_at"),
        "rule": "EXACT_2_2_FOLLOW_24H_MOMENTUM_SIGN",
        "historical_evidence_horizons_hours": [1, 3],
        "shadow_only": True,
        "can_override_production": False,
        "can_execute": False,
        "research_only": True,
        "live_execution": False,
    }
    if not d.get("ok"):
        base["reason"] = "PRODUCTION_DECISION_UNAVAILABLE"
        return base

    lv = d.get("direction_votes_long")
    sv = d.get("direction_votes_short")
    exact_tie = lv == 2 and sv == 2
    no_consensus = d.get("decision") == "WAIT" and d.get("wait_reason") == "NO_DIRECTIONAL_CONSENSUS"
    momentum = base["momentum_24h_pct"]

    if not no_consensus:
        base["reason"] = "PRODUCTION_NOT_NO_CONSENSUS_WAIT"
        return base
    if not exact_tie:
        base["reason"] = "NOT_EXACT_2_2_TIE"
        return base
    if momentum is None:
        base["reason"] = "MOMENTUM_24H_UNAVAILABLE"
        return base

    base.update({
        "status": "SHADOW_SIGNAL",
        "direction": "LONG" if momentum >= 0 else "SHORT",
        "reason": "PREDECLARED_MOMENTUM_TIEBREAK_FOR_PROSPECTIVE_VALIDATION",
    })
    return base


def install(atlas):
    base_decision = atlas.production_decision

    def consensus_tiebreak_shadow(symbol):
        decision = base_decision(symbol)
        return build_shadow_from_decision(decision)

    atlas.consensus_tiebreak_shadow = consensus_tiebreak_shadow
    atlas.CONSENSUS_TIEBREAK_SHADOW_VERSION = VERSION
    return {
        "enabled": True,
        "version": VERSION,
        "rule": "EXACT_2_2_FOLLOW_24H_MOMENTUM_SIGN",
        "horizons_hours": list(HORIZONS_HOURS),
        "shadow_only": True,
        "can_override_production": False,
        "production_threshold_changed": False,
        "live_execution": False,
    }
