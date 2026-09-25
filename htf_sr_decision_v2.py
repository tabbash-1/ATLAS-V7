"""ATLAS HTF neutral-regime + support/resistance decision layer V2.

Purpose
-------
The legacy HTF thesis fails closed whenever 4H and 12H are not both explicitly
LONG/SHORT in the same direction. That is correct for true opposition, but it
also erases an otherwise qualified 4H trend when 12H is merely neutral/ranging.

This overlay is intentionally narrow:
* it NEVER changes scores, thresholds, risk, stops or targets;
* it NEVER flips a direction against 4H;
* it NEVER promotes a setup whose pre-HTF decision was not already actionable;
* it NEVER promotes when 12H is explicitly opposite, 1D is strongly opposite,
  1H does not confirm, data are degraded, or canonical geometry is not ready;
* it exposes a deterministic S/R ladder so local and major levels are visible
  as one hierarchy instead of competing opaque values.

This is a Production decision-semantic fix, not an outcome-fitting rule.
"""
from __future__ import annotations

from typing import Any

VERSION = "HTF_SR_DECISION_V3_TRADER_BRAIN_AUTHORITY"
PRODUCT_HORIZON = "4-12H"


def _norm(value: Any) -> str:
    return str(value or "").strip().upper()


def _f(value: Any, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _geometry_ready(row: dict[str, Any]) -> bool:
    htf = row.get("htf_core_geometry") or {}
    if htf:
        return htf.get("ready") is True
    analyst = row.get("analyst_output") or {}
    canonical = analyst.get("geometry_readiness") or {}
    if canonical:
        return canonical.get("ready") is True
    legacy = row.get("geometry_gate") or {}
    return legacy.get("qualified") is True


def _timeframe_weight(tf: str) -> float:
    return {"1h": 1.0, "4h": 2.0, "12h": 3.0, "1d": 4.0}.get(tf, 1.0)


def _source_weight(source: str) -> float:
    return {
        "LAST_SWING_HIGH": 2.0,
        "LAST_SWING_LOW": 2.0,
        "EMA20": 1.0,
        "EMA50": 1.25,
    }.get(source, 1.0)


def build_sr_ladder(thesis: dict[str, Any]) -> dict[str, Any]:
    """Build S1-S3 / R1-R3 from all canonical frame structure levels.

    Nearby levels are clustered so a 4H swing and a 12H EMA at nearly the same
    price become one confluence zone rather than two contradictory levels.
    S1/R1 are nearest to price; S3/R3 are farther away.
    """
    frames = thesis.get("frames") or {}
    price = _f((frames.get("1h") or {}).get("price"))
    if not price or price <= 0:
        return {
            "version": VERSION,
            "status": "UNAVAILABLE",
            "price": price,
            "supports": [],
            "resistances": [],
        }

    atr = _f((frames.get("1h") or {}).get("atr14")) or _f((frames.get("4h") or {}).get("atr14")) or 0.0
    tolerance = max(price * 0.0015, atr * 0.25)
    raw: list[dict[str, Any]] = []
    for tf in ("1h", "4h", "12h", "1d"):
        state = frames.get(tf) or {}
        for field in ("last_swing_low", "last_swing_high", "ema20", "ema50"):
            level = _f(state.get(field))
            if level is None or level <= 0:
                continue
            source = field.upper()
            raw.append({
                "price": level,
                "timeframe": tf,
                "source": source,
                "weight": _timeframe_weight(tf) * _source_weight(source),
            })

    raw.sort(key=lambda x: x["price"])
    clusters: list[list[dict[str, Any]]] = []
    for item in raw:
        if not clusters:
            clusters.append([item])
            continue
        prev = clusters[-1]
        center = sum(x["price"] * x["weight"] for x in prev) / sum(x["weight"] for x in prev)
        if abs(item["price"] - center) <= tolerance:
            prev.append(item)
        else:
            clusters.append([item])

    zones: list[dict[str, Any]] = []
    for members in clusters:
        total_weight = sum(x["weight"] for x in members)
        center = sum(x["price"] * x["weight"] for x in members) / total_weight
        zones.append({
            "price": round(center, 10),
            "strength": round(total_weight, 3),
            "confluence_count": len(members),
            "timeframes": sorted({x["timeframe"] for x in members}, key=lambda x: ("1h", "4h", "12h", "1d").index(x)),
            "sources": sorted({x["source"] for x in members}),
            "members": members,
        })

    supports = sorted((z for z in zones if z["price"] < price), key=lambda z: z["price"], reverse=True)[:3]
    resistances = sorted((z for z in zones if z["price"] > price), key=lambda z: z["price"])[:3]
    for idx, zone in enumerate(supports, 1):
        zone["label"] = f"S{idx}"
        zone["distance_pct"] = round((price - zone["price"]) / price * 100, 4)
    for idx, zone in enumerate(resistances, 1):
        zone["label"] = f"R{idx}"
        zone["distance_pct"] = round((zone["price"] - price) / price * 100, 4)

    return {
        "version": VERSION,
        "status": "READY",
        "price": price,
        "cluster_tolerance": round(tolerance, 10),
        "supports": supports,
        "resistances": resistances,
        "primary_support": supports[0] if supports else None,
        "primary_resistance": resistances[0] if resistances else None,
        "all_levels_are_context_only": True,
        "score_changed": False,
        "threshold_changed": False,
        "geometry_changed": False,
    }


def assess(row: dict[str, Any]) -> dict[str, Any]:
    thesis = row.get("htf_thesis") or {}
    frames = thesis.get("frames") or {}
    b4 = _norm((frames.get("4h") or {}).get("bias"))
    b12 = _norm((frames.get("12h") or {}).get("bias"))
    b1 = _norm((frames.get("1h") or {}).get("bias"))
    bd = _norm((frames.get("1d") or {}).get("bias"))
    d1_conf = _norm((frames.get("1d") or {}).get("confidence"))
    impulse4 = _norm((frames.get("4h") or {}).get("impulse"))
    volume4 = _norm((frames.get("4h") or {}).get("volume_state"))
    proposed = _norm(row.get("candidate_direction") or row.get("entry_confirmation_direction"))
    pre_htf = _norm(row.get("pre_htf_actionable_decision"))
    geometry_ready = _geometry_ready(row)
    degraded = bool(row.get("data_degraded", False))
    ladder = build_sr_ladder(thesis)

    blockers: list[str] = []
    direction = b4 if b4 in {"LONG", "SHORT"} else None
    neutral_12h = b12 == "NEUTRAL"

    if direction is None:
        blockers.append("4H_DIRECTION_UNRESOLVED")
    if not neutral_12h:
        blockers.append("12H_NOT_NEUTRAL")
    if direction and proposed != direction:
        blockers.append("1H_OR_SCORE_DIRECTION_NOT_4H")
    if direction and b1 in {"LONG", "SHORT"} and b1 != direction:
        blockers.append("1H_STRUCTURE_OPPOSES_4H")
    if direction:
        expected_impulse = "BULLISH" if direction == "LONG" else "BEARISH"
        opposite_impulse = "BEARISH" if direction == "LONG" else "BULLISH"
        if impulse4 == opposite_impulse and volume4 == "EXPANDING":
            blockers.append("4H_COUNTER_IMPULSE_WITH_VOLUME")
        if bd in {"LONG", "SHORT"} and bd != direction and d1_conf == "STRONG":
            blockers.append("1D_MACRO_STRONGLY_OPPOSES_4H")
    if not geometry_ready:
        blockers.append("CANONICAL_GEOMETRY_NOT_READY")
    if degraded:
        blockers.append("DATA_DEGRADED")

    if row.get("production_signal_qualified") is not True:
        blockers.append("PRODUCTION_SIGNAL_NOT_QUALIFIED")
    if pre_htf not in {"LONG", "SHORT"}:
        blockers.append("PRE_HTF_DECISION_NOT_ACTIONABLE")

    blockers = list(dict.fromkeys(blockers))
    eligible = direction is not None and not blockers
    return {
        "version": VERSION,
        "eligible": eligible,
        "direction": direction if eligible else None,
        "regime": "4H_DIRECTIONAL_12H_NEUTRAL" if neutral_12h and direction else "NOT_CONDITIONAL_NEUTRAL_REGIME",
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else None,
        "pre_htf_action": pre_htf if pre_htf in {"LONG", "SHORT"} else "WAIT",
        "candidate_direction": proposed if proposed in {"LONG", "SHORT"} else None,
        "legacy_pre_htf_action": pre_htf if pre_htf in {"LONG", "SHORT"} else "WAIT",
        "score_is_authority": False,
        "canonical_geometry_ready": geometry_ready,
        "support_resistance_ladder": ladder,
        "score_changed": False,
        "threshold_changed": False,
        "geometry_changed": False,
        "live_execution": False,
    }


def apply(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row, dict) or not row.get("ok"):
        return row
    out = dict(row)
    thesis = out.get("htf_thesis") or {}
    out["support_resistance_ladder"] = build_sr_ladder(thesis)
    verdict = assess(out)
    out["htf_sr_decision_v2"] = verdict
    out["htf_alignment_class"] = _norm((thesis or {}).get("direction_alignment")) or _norm(out.get("direction_alignment")) or None

    if not verdict["eligible"]:
        return out

    direction = verdict["direction"]
    # Restore only the decision that existed before the binary HTF neutral/range
    # collapse. Nothing here creates a score-qualified decision from scratch.
    out["product_direction"] = direction
    out["entry_confirmation_direction"] = direction
    out["direction_alignment"] = "ALIGNED"
    out["htf_alignment_class"] = "CONDITIONAL_ALIGNED_12H_NEUTRAL"
    out["conditional_htf_alignment"] = True
    out["actionable_decision"] = direction
    out["actionable_reason"] = "HTF_4H_DIRECTIONAL_12H_NEUTRAL_1H_CONFIRMED"
    out["analysis_ready"] = True
    out["setup_ready"] = True
    # Preserve execution semantics: this only restores analytical permission.
    # Downstream quality, structure, geometry and final gates still decide trade_ready.
    out["can_execute"] = bool(out.get("can_execute", False))

    t = dict(thesis)
    t.update({
        "status": "PASS",
        "direction": direction,
        "product_direction": direction,
        "entry_confirmation_direction": direction,
        "direction_alignment": "CONDITIONAL_ALIGNED",
        "alignment_class": "4H_DIRECTIONAL_12H_NEUTRAL",
        "reason": "HTF_CONDITIONAL_12H_NEUTRAL_ACCEPTED",
        "support_resistance_ladder": out["support_resistance_ladder"],
        "score_changed": False,
        "threshold_changed": False,
    })
    out["htf_thesis"] = t
    return out


def install(atlas):
    if getattr(atlas, "_HTF_SR_DECISION_V2_INSTALLED", False):
        return getattr(atlas, "HTF_SR_DECISION_V2_STATE", {"enabled": True, "version": VERSION})
    original = atlas.production_decision

    def wrapped(symbol):
        return apply(original(symbol))

    atlas.production_decision = wrapped
    atlas._HTF_SR_DECISION_V2_INSTALLED = True
    state = {
        "enabled": True,
        "version": VERSION,
        "product_horizon": PRODUCT_HORIZON,
        "policy": "4H directional + 12H neutral may preserve directional thesis with 1H agreement, no strong 1D opposition and valid geometry; legacy score/pre-HTF action are evidence only",
        "score_changed": False,
        "threshold_changed": False,
        "risk_changed": False,
        "live_execution": False,
    }
    atlas.HTF_SR_DECISION_V2_STATE = state
    return state
