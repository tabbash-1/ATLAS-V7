"""Bridge production cloud-forward observations into ATLAS confluence memory.

The cloud research lane writes champion_challenger_forward.jsonl, while Master
Conviction historical evidence reads confluence_memory.jsonl via
/api/confluence/similar. Without this bridge the two research pipelines can both
work correctly yet Master Conviction can remain at historical n=0 indefinitely.

This module mirrors only newly stored CLOUD_FORWARD observations. It never
changes signal scores, thresholds, alerts, trade plans, or live execution.
"""


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_confluence_payload(row):
    """Translate one frozen cloud-forward row into confluence-memory schema."""
    if not isinstance(row, dict):
        return None
    symbol = str(row.get("symbol") or "").upper().replace("BINANCE:", "")
    direction = str(row.get("direction") or "").upper()
    price = _fnum(row.get("entry"))
    if not symbol or direction not in ("LONG", "SHORT") or not price or price <= 0:
        return None

    signal = "BUY" if direction == "LONG" else "SELL"
    score = _fnum(row.get("final_score"))
    if score is None:
        score = _fnum(row.get("champion_score"))

    research_only = bool(row.get("research_sampling_lane")) or str(
        row.get("execution_decision") or ""
    ).upper() == "RESEARCH_OBSERVATION_ONLY"

    return {
        "symbol": symbol,
        "price": price,
        "signal": signal,
        "base_signal": signal,
        "confidence": score,
        "gate_state": "RESEARCH" if research_only else "PASS",
        "gate_reason": str(row.get("playbook_primary") or row.get("execution_decision") or "CLOUD_FORWARD"),
        "support_strength": row.get("support_strength"),
        "support_distance_pct": row.get("support_distance_pct"),
        "resistance_strength": row.get("resistance_strength"),
        "resistance_distance_pct": row.get("resistance_distance_pct"),
        "relative_volume": row.get("relative_volume"),
        "volume_quality": row.get("volume_quality"),
        "breakout_score": row.get("breakout_score"),
        "breakdown_score": row.get("breakdown_score"),
        "futures_score": row.get("futures_score"),
        "oi_change_pct": row.get("oi_change_pct"),
        "taker_ratio": row.get("taker_ratio"),
        "orderbook_imbalance": row.get("orderbook_imbalance"),
        "liquidity_score": row.get("liquidity_score"),
        "master_score": score,
        "master_decision": str(row.get("execution_decision") or "CLOUD_FORWARD_RESEARCH"),
        "final_score": score,
        "final_decision": str(row.get("execution_decision") or "CLOUD_FORWARD_RESEARCH"),
        "trade_plan_status": row.get("trade_plan_status"),
        "rr_tp1": row.get("rr_tp1"),
        "rr_tp2": row.get("rr_tp2"),
        "regime": row.get("regime"),
        "relative_strength_score": row.get("relative_strength_score"),
        "opportunity_score": row.get("opportunity_score"),
        "cloud_memory_bridge": True,
        "research_sampling_lane": bool(row.get("research_sampling_lane")),
    }


def install(collector):
    """Install a fail-open mirror around collector.forward_observe exactly once."""
    if getattr(collector, "_RESEARCH_MEMORY_BRIDGE_INSTALLED", False):
        return getattr(collector, "RESEARCH_MEMORY_BRIDGE_STATE", {})

    original = collector.forward_observe
    state = {
        "enabled": True,
        "forward_stored": 0,
        "mirror_attempts": 0,
        "mirrored": 0,
        "mirror_errors": 0,
        "skipped_non_cloud": 0,
        "skipped_deduped": 0,
        "last_error": None,
        "last_symbol": None,
    }

    def bridged_forward_observe(row):
        result = original(row)
        if isinstance(result, dict) and result.get("stored") is False:
            state["skipped_deduped"] += 1
            return result

        state["forward_stored"] += 1
        source = str((row or {}).get("auto_source") or "")
        cloud_row = source.startswith("CLOUD_FORWARD") or bool((row or {}).get("research_sampling_lane"))
        if not cloud_row:
            state["skipped_non_cloud"] += 1
            return result

        payload = build_confluence_payload(row)
        if payload is None:
            state["mirror_errors"] += 1
            state["last_error"] = "invalid cloud-forward row for confluence mirror"
            return result

        state["mirror_attempts"] += 1
        state["last_symbol"] = payload["symbol"]
        try:
            collector.confluence_observe(payload)
            state["mirrored"] += 1
            state["last_error"] = None
        except Exception as exc:  # fail-open: never damage forward collection
            state["mirror_errors"] += 1
            state["last_error"] = f"{type(exc).__name__}: {exc}"
        return result

    collector.forward_observe = bridged_forward_observe
    collector.RESEARCH_MEMORY_BRIDGE_STATE = state
    collector._RESEARCH_MEMORY_BRIDGE_INSTALLED = True
    return state
