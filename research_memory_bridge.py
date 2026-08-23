"""Bridge production cloud-forward observations into ATLAS confluence memory.

This module also reconciles Pattern Memory forward returns against the canonical
cloud-forward archive and enforces a strict maturity chain. A 24h result is not
counted unless 1h, 4h and 12h are also present; similarly for every later
horizon. This prevents sparse confluence observations from creating impossible
maturity states such as 24h matured while 12h is missing.
"""

HORIZONS = (1, 4, 12, 24)
MATCH_WINDOW_MS = 10 * 60 * 1000
PRICE_TOLERANCE_PCT = 0.75


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_cloud_forward(row):
    source = str((row or {}).get("auto_source") or "")
    return source.startswith("CLOUD_FORWARD") or bool((row or {}).get("research_sampling_lane"))


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


def _strict_chain(fr):
    """Return a monotonic horizon map plus any rejected later horizons."""
    source = dict(fr or {})
    clean = {}
    missing_seen = False
    rejected = []
    for h in HORIZONS:
        key = str(h)
        value = _fnum(source.get(key))
        if missing_seen or value is None:
            if value is not None:
                rejected.append(key)
            clean[key] = None
            missing_seen = True
        else:
            clean[key] = value
    return clean, rejected


def _match_forward(memory_row, forward_rows):
    symbol = str(memory_row.get("symbol") or "").upper()
    mts = int(memory_row.get("captured_at_ms") or 0)
    mprice = _fnum(memory_row.get("price"))
    best = None
    best_dt = None
    for row in forward_rows or []:
        if not _is_cloud_forward(row) or str(row.get("symbol") or "").upper() != symbol:
            continue
        ts = int(row.get("captured_at_ms") or row.get("event_at_ms") or 0)
        if not mts or not ts:
            continue
        dt = abs(ts - mts)
        if dt > MATCH_WINDOW_MS:
            continue
        entry = _fnum(row.get("entry"))
        if mprice and entry:
            diff = abs(entry / mprice - 1) * 100
            if diff > PRICE_TOLERANCE_PCT:
                continue
        if best is None or dt < best_dt:
            best = row
            best_dt = dt
    return best


def reconcile_confluence_rows(confluence_rows, forward_rows):
    """Use canonical forward returns when linkable, then enforce strict maturity."""
    out = []
    metrics = {"rows": 0, "linked_to_forward": 0, "gap_rows": 0, "rejected_horizons": 0}
    for row in confluence_rows or []:
        x = dict(row)
        metrics["rows"] += 1
        source_fr = x.get("forward_return_pct") or {}
        match = _match_forward(x, forward_rows)
        if match is not None and (match.get("forward_return_pct") or {}):
            source_fr = match.get("forward_return_pct") or {}
            metrics["linked_to_forward"] += 1
            x["forward_evidence_source"] = "CANONICAL_FORWARD_ARCHIVE"
        else:
            x["forward_evidence_source"] = "CONFLUENCE_FALLBACK"
        clean, rejected = _strict_chain(source_fr)
        if rejected:
            metrics["gap_rows"] += 1
            metrics["rejected_horizons"] += len(rejected)
        x["forward_return_pct"] = clean
        x["maturity_integrity"] = {
            "strict_chain": True,
            "rejected_horizons": rejected,
            "valid_through": max((h for h in HORIZONS if clean[str(h)] is not None), default=0),
        }
        out.append(x)
    return out, metrics


def install(collector):
    """Install cloud mirror and Pattern Memory integrity reconciliation once."""
    if getattr(collector, "_RESEARCH_MEMORY_BRIDGE_INSTALLED", False):
        return getattr(collector, "RESEARCH_MEMORY_BRIDGE_STATE", {})

    original_forward_observe = collector.forward_observe
    original_confluence_forward_rows = getattr(collector, "confluence_forward_rows", None)
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
        "integrity": {"enabled": bool(original_confluence_forward_rows), "rows": 0, "linked_to_forward": 0, "gap_rows": 0, "rejected_horizons": 0},
    }

    def bridged_forward_observe(row):
        result = original_forward_observe(row)
        if isinstance(result, dict) and result.get("stored") is False:
            state["skipped_deduped"] += 1
            return result

        state["forward_stored"] += 1
        if not _is_cloud_forward(row):
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

    if original_confluence_forward_rows is not None:
        def integrity_confluence_forward_rows(symbol=None):
            raw = original_confluence_forward_rows(symbol)
            try:
                forward_rows = collector.read_forward() if hasattr(collector, "read_forward") else []
                reconciled, metrics = reconcile_confluence_rows(raw, forward_rows)
                state["integrity"] = {"enabled": True, **metrics}
                return reconciled
            except Exception as exc:
                # Fail closed for maturity ordering even if archive reconciliation fails.
                reconciled, metrics = reconcile_confluence_rows(raw, [])
                state["integrity"] = {"enabled": True, **metrics, "last_error": f"{type(exc).__name__}: {exc}"}
                return reconciled
        collector.confluence_forward_rows = integrity_confluence_forward_rows

    collector.forward_observe = bridged_forward_observe
    collector.RESEARCH_MEMORY_BRIDGE_STATE = state
    collector._RESEARCH_MEMORY_BRIDGE_INSTALLED = True
    return state
