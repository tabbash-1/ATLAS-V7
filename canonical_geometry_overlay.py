"""Canonical geometry truth overlay for ATLAS 4-12H analysis.

Repairs the legacy mismatch where the decision API could combine Entry/Stop/Target
from one geometry with an R:R value sourced from a different scorer plan. This
overlay never changes Production score, signal threshold, raw qualification, or
live-execution policy. It recomputes geometry readiness only from the exact
Entry/Stop/Target shown by the decision payload and preserves the legacy
`execution_ready` field strictly as a compatibility alias.
"""

VERSION = "ATLAS_CANONICAL_GEOMETRY_TRUTH_V1"
REASON_SCHEMA_VERSION = "ATLAS_GEOMETRY_REASON_CODES_V1"
MIN_RR = 1.0


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _base(status, qualified, reason, blockers, **extra):
    out = {
        "status": status,
        "qualified": qualified,
        "reason": reason,
        "primary_blocker": blockers[0] if blockers else None,
        "blocker_codes": list(blockers),
        "reason_schema_version": REASON_SCHEMA_VERSION,
        "risk_reward": None,
        "min_risk_reward": MIN_RR,
        "version": VERSION,
    }
    out.update(extra)
    return out


def assess(direction, entry, stop, target):
    entry = _num(entry)
    stop = _num(stop)
    target = _num(target)
    checks = {
        "direction_valid": direction in ("LONG", "SHORT"),
        "entry_present": entry is not None,
        "stop_present": stop is not None,
        "target_present": target is not None,
        "stop_correct_side": None,
        "target_correct_side": None,
        "risk_positive": None,
        "rr_meets_minimum": None,
    }

    if direction not in ("LONG", "SHORT"):
        return _base("NOT_APPLICABLE", False, "NO_DIRECTION", ["NO_DIRECTION"], checks=checks)

    missing = []
    if entry is None:
        missing.append("MISSING_ENTRY")
    if stop is None:
        missing.append("MISSING_STOP")
    if target is None:
        missing.append("MISSING_TARGET")
    if missing:
        return _base("BLOCK", False, "GEOMETRY_INCOMPLETE", missing, checks=checks)

    if direction == "LONG":
        checks["stop_correct_side"] = stop < entry
        checks["target_correct_side"] = target > entry
    else:
        checks["stop_correct_side"] = stop > entry
        checks["target_correct_side"] = target < entry

    ordering_blockers = []
    if not checks["stop_correct_side"]:
        ordering_blockers.append("STOP_WRONG_SIDE")
    if not checks["target_correct_side"]:
        ordering_blockers.append("TARGET_WRONG_SIDE")
    if ordering_blockers:
        return _base("BLOCK", False, "INVALID_ENTRY_SL_TP_ORDER", ordering_blockers, checks=checks)

    risk = abs(entry - stop)
    reward = abs(target - entry)
    checks["risk_positive"] = risk > 0
    if not checks["risk_positive"]:
        return _base("BLOCK", False, "ZERO_RISK_GEOMETRY", ["NON_POSITIVE_RISK"], checks=checks)

    rr = reward / risk
    checks["rr_meets_minimum"] = rr >= MIN_RR
    qualified = checks["rr_meets_minimum"]
    return _base(
        "PASS" if qualified else "BLOCK",
        qualified,
        "RR_ONE_TO_ONE_OR_BETTER" if qualified else "RR_BELOW_ONE_TO_ONE",
        [] if qualified else ["RR_BELOW_MINIMUM"],
        risk_reward=round(rr, 6),
        risk=round(risk, 10),
        reward=round(reward, 10),
        rr_source="RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET",
        checks=checks,
    )


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
        payload["geometry_reason_schema_version"] = REASON_SCHEMA_VERSION
        payload["geometry_rr_source"] = "RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET"
        payload["score_or_threshold_changed_by_geometry"] = False

        # Compatibility only. No order routing exists; downstream legacy readers
        # still consume this name as current-entry geometry readiness.
        payload["execution_ready"] = geometry_ready
        payload["actionable_decision"] = direction if geometry_ready else "WAIT"
        if not qualified:
            payload["actionable_reason"] = payload.get("wait_reason") or "SCORE_BELOW_SIGNAL_THRESHOLD"
        elif not geometry_ready:
            payload["actionable_reason"] = geometry.get("primary_blocker") or geometry.get("reason")
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
            matrix["swing"]["geometry_blocker_codes"] = list(geometry.get("blocker_codes") or [])
            matrix["swing"]["actionable_decision"] = direction if geometry_ready else "WAIT"

        payload["analysis_only"] = True
        payload["live_execution"] = False
        return payload

    atlas.production_decision = wrapped
    return {
        "enabled": True,
        "version": VERSION,
        "reason_schema_version": REASON_SCHEMA_VERSION,
        "min_rr": MIN_RR,
        "rr_source": "EXACT_ENTRY_STOP_TARGET",
        "score_threshold_unchanged": True,
        "analysis_only": True,
        "live_execution": False,
    }
