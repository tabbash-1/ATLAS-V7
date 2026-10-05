"""ATLAS Trader Brain V1 — one 4-12H trading lifecycle.

This is the decision-quality layer between market analysis and FINAL_TRADE_GATE.
It does not route orders. It converts existing ATLAS evidence into a trader-like
state: thesis -> location -> setup -> trigger -> geometry -> trade/wait.
Legacy score is evidence only and cannot independently authorize or veto a trade.
"""
from __future__ import annotations

VERSION = "ATLAS_TRADER_BRAIN_V9_REAL_1H_MOMENTUM"
MIN_RR = 2.0
ACCEPTED_ALIGNMENT = {"ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"}
EXPLICIT_CONFLICT_ALIGNMENTS = {"CONFLICT", "HTF_CONFLICT", "OPPOSED", "MISALIGNED", "DIVERGENT"}


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
    root = row.get("trade_plan") or {}
    rr = _num(root.get("rr_tp2"))
    if rr is not None:
        return rr
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


def _one_hour_momentum_confirmed(row, direction):
    """Require actual completed 1H momentum evidence in the product direction.

    Candidate/entry direction agreement is routing metadata, not an independent
    momentum confirmation. MOMENTUM therefore comes only from the canonical 1H
    frame impulse plus a directionally confirming candle/pattern.
    """
    direction = _norm(direction)
    thesis = row.get("htf_thesis") or {}
    frame = ((thesis.get("frames") or {}).get("1h") or {})
    impulse = _norm(frame.get("impulse"))
    candle = frame.get("candle") or {}
    candle_direction = _norm(candle.get("direction"))
    pattern = _norm(candle.get("pattern"))
    if direction == "LONG":
        expected_impulse = "BULLISH"
        expected_candle = "BULLISH"
        accepted_patterns = {"BULLISH_ENGULFING", "HAMMER_REJECTION", "BULLISH_DISPLACEMENT"}
    elif direction == "SHORT":
        expected_impulse = "BEARISH"
        expected_candle = "BEARISH"
        accepted_patterns = {"BEARISH_ENGULFING", "SHOOTING_STAR_REJECTION", "BEARISH_DISPLACEMENT"}
    else:
        expected_impulse = None
        expected_candle = None
        accepted_patterns = set()
    confirmed = bool(
        direction in {"LONG", "SHORT"}
        and impulse == expected_impulse
        and (candle_direction == expected_candle or pattern in accepted_patterns)
    )
    return confirmed, {
        "timeframe": "1h",
        "direction": direction or None,
        "impulse": impulse or None,
        "candle_direction": candle_direction or None,
        "candle_pattern": pattern or None,
        "accepted_patterns": sorted(accepted_patterns),
        "rule": "1H_IMPULSE_PLUS_DIRECTIONAL_CANDLE_OR_PATTERN",
        "candidate_direction_agreement_is_momentum": False,
    }


def _pullback_resumption_confirmed(row, direction):
    """Require fresh 1H resumption in the HTF direction before a trend pullback is ready."""
    direction = _norm(direction)
    thesis = row.get("htf_thesis") or {}
    frame = ((thesis.get("frames") or {}).get("1h") or {})
    impulse = _norm(frame.get("impulse"))
    bias = _norm(frame.get("bias") or frame.get("structural_direction"))
    candle = frame.get("candle") or {}
    candle_direction = _norm(candle.get("direction"))
    pattern = _norm(candle.get("pattern"))
    if direction == "LONG":
        expected_impulse = "BULLISH"
        expected_candle = "BULLISH"
        accepted_patterns = {"BULLISH_ENGULFING", "HAMMER_REJECTION", "BULLISH_DISPLACEMENT"}
    elif direction == "SHORT":
        expected_impulse = "BEARISH"
        expected_candle = "BEARISH"
        accepted_patterns = {"BEARISH_ENGULFING", "SHOOTING_STAR_REJECTION", "BEARISH_DISPLACEMENT"}
    else:
        expected_impulse = None
        expected_candle = None
        accepted_patterns = set()
    confirmed = bool(
        direction in {"LONG", "SHORT"}
        and impulse == expected_impulse
        and bias == direction
        and (candle_direction == expected_candle or pattern in accepted_patterns)
    )
    return confirmed, {
        "timeframe": "1h",
        "direction": direction or None,
        "impulse": impulse or None,
        "bias": bias or None,
        "candle_direction": candle_direction or None,
        "candle_pattern": pattern or None,
        "accepted_reversal_or_displacement_patterns": sorted(accepted_patterns),
        "rule": "1H_DIRECTIONAL_BIAS_PLUS_IMPULSE_PLUS_CANDLE_RESUMPTION",
    }


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
    one_hour_momentum_confirmed, one_hour_momentum_evidence = _one_hour_momentum_confirmed(row, product)
    pullback_resumption_confirmed, pullback_resumption_evidence = _pullback_resumption_confirmed(row, product)
    pullback_requires_resumption = bool(product in {"LONG", "SHORT"} and playbook == "TREND_PULLBACK")

    fatal = []
    waits = []
    if product not in {"LONG", "SHORT"}:
        fatal.append("TRADER_NO_DIRECTIONAL_THESIS")
    # Only explicit opposing HTF evidence is a fatal conflict. Missing/neutral/lagging
    # alignment must not be mislabeled as an opposing thesis; downstream trigger and
    # geometry gates still have to pass before TRADE_READY.
    if alignment in EXPLICIT_CONFLICT_ALIGNMENTS:
        fatal.append("TRADER_HTF_CONFLICT")
    elif alignment not in ACCEPTED_ALIGNMENT:
        waits.append("TRADER_WAIT_HTF_ALIGNMENT_EVIDENCE")
    if degraded:
        fatal.append("DATA_DEGRADED")
    if quality_blocked:
        fatal.append("SETUP_QUALITY_GATE_BLOCKED")
    if rr is None or rr < MIN_RR:
        fatal.append("TRADER_RR_BELOW_2R")

    if entry != product and product in {"LONG", "SHORT"}:
        waits.append("TRADER_WAIT_1H_TRIGGER")
    elif product in {"LONG", "SHORT"} and not one_hour_momentum_confirmed:
        waits.append("TRADER_WAIT_1H_MOMENTUM_CONFIRMATION")
    if not geometry_ready:
        waits.append("TRADER_WAIT_VALID_LOCATION")
    if pullback_requires_resumption and not pullback_resumption_confirmed:
        waits.append("TRADER_WAIT_LONG_PULLBACK_RESUMPTION" if product == "LONG" else "TRADER_WAIT_SHORT_PULLBACK_RESUMPTION")

    # Require at least three independent evidence families before TRADE_READY.
    # Score itself is deliberately excluded: it is a summary, not an independent confirmation.
    score_attr = row.get("score_attribution") or ((row.get("decision_provenance") or {}).get("score_attribution") or {})
    confirmations = []
    # Evidence is counted by independent FAMILY, not by raw checks. HTF direction
    # and structural location are one STRUCTURE family and must never be double-counted.
    if product in {"LONG", "SHORT"} and alignment in ACCEPTED_ALIGNMENT and geometry_ready:
        confirmations.append("STRUCTURE")
    momentum_ready = bool(
        entry == product
        and product in {"LONG", "SHORT"}
        and one_hour_momentum_confirmed
    )
    if pullback_requires_resumption:
        momentum_ready = bool(momentum_ready and pullback_resumption_confirmed)
    if momentum_ready:
        confirmations.append("MOMENTUM")
    try:
        rv = float(row.get("relative_volume"))
    except (TypeError, ValueError):
        rv = None
    if rv is not None and rv >= 1.0:
        confirmations.append("VOLUME")
    futures_available = row.get("futures_available") is True
    futures_reason = _norm(score_attr.get("futures_reason"))
    if futures_available and futures_reason == "ALIGNED":
        confirmations.append("DERIVATIVES")
    confirmations = list(dict.fromkeys(confirmations))
    if len(confirmations) < 3:
        waits.append("TRADER_WAIT_MIN_3_INDEPENDENT_CONFIRMATIONS")

    extension_reason = _norm(score_attr.get("extension_guard_reason"))
    extension_adjustment = _num(score_attr.get("extension_guard_adjustment"))
    extension_flag = any(token in extension_reason for token in ("BLOWOFF", "OVEREXTEND", "CHASE", "LATE_ENTRY"))
    legacy_extension_flag = any(
        token in _norm(quality.get("reason") or row.get("wait_reason") or row.get("actionable_reason"))
        for token in ("OVEREXTEND", "CHASE", "LATE_ENTRY")
    )
    overextended = bool(extension_flag or legacy_extension_flag)
    if extension_flag and mode == "NOW":
        waits.append("TRADER_WAIT_PULLBACK_RETEST")
    if overextended:
        waits.append("TRADER_NO_CHASE")

    if fatal:
        stage = "NO_TRADE"
    elif waits:
        trigger_waits = {"TRADER_WAIT_1H_TRIGGER", "TRADER_WAIT_1H_MOMENTUM_CONFIRMATION", "TRADER_WAIT_LONG_PULLBACK_RESUMPTION", "TRADER_WAIT_SHORT_PULLBACK_RESUMPTION"}
        stage = "WAIT_TRIGGER" if any(w in trigger_waits for w in waits) else "WAIT_LOCATION"
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
        "pullback_resumption_required": pullback_requires_resumption,
        "pullback_resumption_confirmed": pullback_resumption_confirmed,
        "pullback_resumption_evidence": pullback_resumption_evidence,
        # Backward-compatible fields for existing Production diagnostics.
        "short_pullback_resumption_confirmed": pullback_resumption_confirmed if product == "SHORT" else None,
        "short_pullback_resumption_evidence": pullback_resumption_evidence if product == "SHORT" else None,
        "long_pullback_resumption_confirmed": pullback_resumption_confirmed if product == "LONG" else None,
        "long_pullback_resumption_evidence": pullback_resumption_evidence if product == "LONG" else None,
        "one_hour_momentum_confirmed": one_hour_momentum_confirmed,
        "one_hour_momentum_evidence": one_hour_momentum_evidence,
        "entry_direction_aligned": entry == product and product in {"LONG", "SHORT"},
        "entry_trigger_ready": momentum_ready,
        "entry_mode": mode or None,
        "desired_entry_mode": "PULLBACK_RETEST" if overextended and mode == "NOW" else (mode or None),
        "extension_guard_reason": extension_reason or None,
        "extension_guard_adjustment": extension_adjustment,
        "geometry_ready": geometry_ready,
        "rr_tp2": round(rr, 3) if rr is not None else None,
        "minimum_rr_required": MIN_RR,
        "independent_confirmations": confirmations,
        "independent_confirmation_count": len(confirmations),
        "minimum_independent_confirmations_required": 3,
        "independent_confirmation_families": ["STRUCTURE", "MOMENTUM", "VOLUME", "DERIVATIVES"],
        "structure_double_counting_allowed": False,
        "fatal_blockers": list(dict.fromkeys(fatal)),
        "wait_blockers": list(dict.fromkeys(waits)),
        "legacy_score": _num(row.get("score") or (row.get("analyst_output") or {}).get("confidence")),
        "score_is_authority": False,
        "decision_rule": "THESIS_LOCATION_SETUP_TRIGGER_GEOMETRY",
        "analysis_only": True,
        "live_execution": False,
    }
