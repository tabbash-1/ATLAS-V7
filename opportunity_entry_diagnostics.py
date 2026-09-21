"""ATLAS opportunity/entry diagnostic classifier.

Read-only research module. It does not alter Production qualification, thresholds,
or order routing. It separates direction quality from entry quality so historical
4-12H replays can explain missed opportunities instead of collapsing everything
into WAIT.
"""

VERSION = "OPPORTUNITY_ENTRY_DIAGNOSTICS_V1"
HORIZONS_H = (4, 8, 12)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _directional_return(direction, entry, future_price):
    entry, future_price = _f(entry), _f(future_price)
    if direction not in ("LONG", "SHORT") or not entry or future_price is None:
        return None
    raw = (future_price / entry - 1.0) * 100.0
    return raw if direction == "LONG" else -raw


def classify(decision, forward_prices, opportunity_move_pct=1.0):
    """Classify a historical decision using only prices that occur after decision time.

    forward_prices accepts {4: price, 8: price, 12: price}. The caller is responsible
    for timestamp integrity. No forward value is used to create the original signal.
    """
    row = decision if isinstance(decision, dict) else {}
    direction = row.get("candidate_direction")
    entry = _f(row.get("entry"))
    if direction not in ("LONG", "SHORT") or entry is None:
        return {"version": VERSION, "classification": "NO_DIRECTION", "direction_quality": "UNAVAILABLE",
                "entry_quality": "UNAVAILABLE", "forward_returns_pct": {}, "research_only": True}

    returns = {}
    for h in HORIZONS_H:
        if h in (forward_prices or {}):
            r = _directional_return(direction, entry, forward_prices[h])
            if r is not None:
                returns[h] = round(r, 4)

    if not returns:
        return {"version": VERSION, "classification": "UNSETTLED", "direction_quality": "UNSETTLED",
                "entry_quality": "UNSETTLED", "forward_returns_pct": {}, "research_only": True}

    best = max(returns.values())
    worst = min(returns.values())
    qualified = bool(row.get("production_signal_qualified"))
    ready = bool(row.get("execution_ready") or row.get("trade_ready"))
    plan = row.get("trade_plan") or {}
    mode = plan.get("entry_mode") or row.get("entry_mode")
    threshold = abs(float(opportunity_move_pct))

    direction_right = best >= threshold
    direction_wrong = worst <= -threshold and best < threshold
    if direction_right and ready:
        classification = "CORRECT_TRADE"
        entry_quality = "EXECUTED_OR_READY"
    elif direction_right:
        classification = "MISSED_OPPORTUNITY"
        entry_quality = "BLOCKED_OR_LATE"
    elif direction_wrong and ready:
        classification = "WRONG_DIRECTION"
        entry_quality = "ENTRY_EXPOSED_BAD_DIRECTION"
    elif direction_wrong:
        classification = "WRONG_DIRECTION_AVOIDED"
        entry_quality = "NOT_ENTERED"
    else:
        classification = "NO_MEANINGFUL_EDGE"
        entry_quality = "NEUTRAL"

    return {
        "version": VERSION,
        "classification": classification,
        "direction_quality": "RIGHT" if direction_right else "WRONG" if direction_wrong else "NEUTRAL",
        "entry_quality": entry_quality,
        "candidate_direction": direction,
        "production_qualified": qualified,
        "execution_ready": ready,
        "entry_mode": mode,
        "entry": entry,
        "forward_returns_pct": returns,
        "best_directional_return_pct": round(best, 4),
        "worst_directional_return_pct": round(worst, 4),
        "blocking_gates": list(row.get("blocking_gates") or (row.get("final_trade_gate") or {}).get("blocking_gates") or []),
        "opportunity_move_threshold_pct": threshold,
        "production_mutated": False,
        "research_only": True,
    }


def summarize(rows):
    counts = {}
    for row in rows or []:
        key = (row or {}).get("classification", "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    missed = counts.get("MISSED_OPPORTUNITY", 0)
    correct = counts.get("CORRECT_TRADE", 0)
    denominator = missed + correct
    return {
        "version": VERSION,
        "total": total,
        "counts": counts,
        "opportunity_capture_rate": round(correct / denominator, 4) if denominator else None,
        "missed_opportunity_rate": round(missed / denominator, 4) if denominator else None,
        "research_only": True,
    }
