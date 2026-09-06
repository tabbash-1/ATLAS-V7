"""Canonical geometry truth overlay for ATLAS 4-12H analysis.

Repairs the legacy mismatch where the decision API could combine Entry/Stop/Target
from one geometry with an R:R value sourced from a different scorer plan. This
overlay never changes Production score, signal threshold, raw qualification, or
live-execution policy. It recomputes geometry readiness only from the exact
Entry/Stop/Target shown by the decision payload and preserves the legacy
`execution_ready` field strictly as a compatibility alias.
"""

VERSION = "ATLAS_CANONICAL_GEOMETRY_TRUTH_V1"
MIN_RR = 1.0


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assess(direction, entry, stop, target):
    entry = _num(entry)
    stop = _num(stop)
    target = _num(target)

    if direction not in ("LONG", "SHORT"):
        return {
            "status": "NOT_APPLICABLE",
            "qualified": False,
            "reason": "NO_DIRECTION",
            "risk_reward": None,
            "version": VERSION,
        }
    if None in (entry, stop, target):
        return {
            "status": "BLOCK",
            "qualified": False,
            "reason": "GEOMETRY_INCOMPLETE",
            "risk_reward": None,
            "min_risk_reward": MIN_RR,
            "version": VERSION,
        }

    directional = (
        direction == "LONG" and stop < entry < target
    ) or (
        direction == "SHORT" and target < entry < stop
    )
    if not directional:
        return {
            "status": "BLOCK",
            "qualified": False,
            "reason": "INVALID_ENTRY_SL_TP_ORDER",
            "risk_reward": None,
            "min_risk_reward": MIN_RR,
            "version": VERSION,
        }

    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = reward / risk if risk > 0 else None
    if rr is None:
        return {
            "status": "BLOCK",
            "qualified": False,
            "reason": "ZERO_RISK_GEOMETRY",
            "risk_reward": None,
            "min_risk_reward": MIN_RR,
            "version": VERSION,
        }

    qualified = rr >= MIN_RR
    return {
        "status": "PASS" if qualified else "BLOCK",
        "qualified": qualified,
        "reason": "RR_ONE_TO_ONE_OR_BETTER" if qualified else "RR_BELOW_ONE_TO_ONE",
        "risk_reward": round(rr, 6),
        "min_risk_reward": MIN_RR,
        "risk": round(risk, 10),
        "reward": round(reward, 10),
        "rr_source": "RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET",
        "version": VERSION,
    }


def install(atlas):
    original = atlas.production_decision

    def wrapped(symbol):
        payload = original(symbol)
        if not isinstance(payload, dict) or not payload.get("ok"):
            return payload

        direction = payload.get("candidate_direction")
        geometry = assess(
            direction,
            payload.get("entry"),
            payload.get("stop_loss"),
            payload.get("take_profit"),
        )
        qualified = bool(payload.get("production_signal_qualified"))
        geometry_ready = bool(qualified and geometry.get("qualified"))

        payload["geometry_gate"] = geometry
        payload["risk_reward"] = geometry.get("risk_reward")
        payload["geometry_ready"] = geometry_ready
        payload["raw_geometry_ready"] = geometry_ready
        payload["geometry_version"] = VERSION
        payload["geometry_rr_source"] = "RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET"
        payload["score_or_threshold_changed_by_geometry"] = False

        # Compatibility only. No order routing exists; downstream legacy readers
        # still consume this name as current-entry geometry readiness.
        payload["execution_ready"] = geometry_ready
        payload["actionable_decision"] = direction if geometry_ready else "WAIT"
        if not qualified:
            payload["actionable_reason"] = payload.get("wait_reason") or "SCORE_BELOW_SIGNAL_THRESHOLD"
        elif not geometry_ready:
            payload["actionable_reason"] = geometry.get("reason")
        else:
            payload["actionable_reason"] = "ANALYSIS_GEOMETRY_READY"

        if qualified and not geometry_ready:
            payload["trade_plan_status"] = "SCORE_QUALIFIED_GEOMETRY_BLOCKED"
        elif geometry_ready:
            payload["trade_plan_status"] = "ANALYSIS_GEOMETRY_READY"

        matrix = payload.get("timeframe_matrix")
        if isinstance(matrix, dict) and isinstance(matrix.get("swing"), dict):
            matrix["swing"]["risk_reward"] = geometry.get("risk_reward")
            matrix["swing"]["execution_ready"] = geometry_ready
            matrix["swing"]["geometry_ready"] = geometry_ready
            matrix["swing"]["actionable_decision"] = direction if geometry_ready else "WAIT"

        payload["analysis_only"] = True
        payload["live_execution"] = False
        return payload

    atlas.production_decision = wrapped
    return {
        "enabled": True,
        "version": VERSION,
        "min_rr": MIN_RR,
        "rr_source": "EXACT_ENTRY_STOP_TARGET",
        "score_threshold_unchanged": True,
        "analysis_only": True,
        "live_execution": False,
    }
