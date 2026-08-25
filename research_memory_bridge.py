"""Bridge production cloud-forward observations into ATLAS Pattern Memory.

Cloud rows are stored with exact forward-observation lineage. Historical rows
created before lineage support can still reconcile by direction + timestamp +
price. All returned maturity is forced through a strict 1h -> 4h -> 12h -> 24h
chain so sparse sampling can never masquerade as mature evidence.

Integrity semantics:
- awaiting_maturity_rows: valid prefix only; later horizons are not available yet.
- sparse_sampling_rows: a later horizon exists after an earlier missing horizon;
  the later value is suppressed from Pattern Memory, but this is not by itself a
  hard corruption signal because market snapshots may be sparse.
- lineage_conflicts: an exact forward id exists but its symbol/direction conflicts
  with the memory row. This is a hard integrity fault and is never fuzzy-matched.
"""

import json
import time

HORIZONS = (1, 4, 12, 24)
MATCH_WINDOW_MS = 10 * 60 * 1000
PRICE_TOLERANCE_PCT = 0.75
MEMORY_DEDUP_MS = 45 * 60 * 1000


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_cloud_forward(row):
    source = str((row or {}).get("auto_source") or "")
    return source.startswith("CLOUD_FORWARD") or bool((row or {}).get("research_sampling_lane"))


def _canonical_forward_result(result, submitted):
    """Return the canonical stored forward row across old/new return shapes."""
    if isinstance(result, dict):
        record = result.get("record")
        if isinstance(record, dict):
            return record
        if result.get("schema") == "ATLAS_FORWARD_V1" and result.get("id"):
            return result
    return submitted


def build_confluence_payload(row):
    """Translate one frozen cloud-forward row into Pattern Memory schema."""
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
        "auto_source": row.get("auto_source"),
        "forward_observation_id": row.get("id"),
        "forward_captured_at_ms": row.get("captured_at_ms"),
        "forward_direction": direction,
    }


def _strict_chain(fr):
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


def _chain_state(clean, rejected):
    """Classify maturity state without treating sparse snapshots as corruption."""
    if rejected:
        return "SPARSE_SAMPLING_GAP"
    if all(clean.get(str(h)) is not None for h in HORIZONS):
        return "COMPLETE_24H"
    if any(clean.get(str(h)) is not None for h in HORIZONS):
        return "AWAITING_LATER_MATURITY"
    return "UNMATURED"


def _memory_direction(row):
    signal = str((row or {}).get("base_signal") or (row or {}).get("signal") or "").upper()
    if signal == "BUY":
        return "LONG"
    if signal == "SELL":
        return "SHORT"
    return str((row or {}).get("forward_direction") or "").upper() or None


def _match_forward(memory_row, forward_rows):
    symbol = str(memory_row.get("symbol") or "").upper()
    expected_direction = _memory_direction(memory_row)
    exact_id = str(memory_row.get("forward_observation_id") or "")

    if exact_id:
        exact_candidates = [row for row in (forward_rows or []) if str(row.get("id") or "") == exact_id]
        if exact_candidates:
            row = exact_candidates[0]
            same_symbol = str(row.get("symbol") or "").upper() == symbol
            same_direction = not expected_direction or str(row.get("direction") or "").upper() == expected_direction
            if same_symbol and same_direction:
                return row, "EXACT_ID", None
            return None, None, "EXACT_ID_LINEAGE_CONFLICT"

    mts = int(memory_row.get("forward_captured_at_ms") or memory_row.get("captured_at_ms") or 0)
    mprice = _fnum(memory_row.get("price"))
    best = None
    best_dt = None
    for row in forward_rows or []:
        if not _is_cloud_forward(row) or str(row.get("symbol") or "").upper() != symbol:
            continue
        if expected_direction and str(row.get("direction") or "").upper() != expected_direction:
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
    return (best, "FUZZY_LEGACY", None) if best is not None else (None, None, None)


def reconcile_confluence_rows(confluence_rows, forward_rows):
    out = []
    metrics = {
        "rows": 0,
        "linked_to_forward": 0,
        "exact_lineage_links": 0,
        "legacy_fuzzy_links": 0,
        "unlinked_rows": 0,
        "awaiting_maturity_rows": 0,
        "complete_24h_rows": 0,
        "sparse_sampling_rows": 0,
        "suppressed_later_horizons": 0,
        "lineage_conflicts": 0,
        "hard_integrity_errors": 0,
        # Backward-compatible names. A 'gap' here means a sparse maturity chain,
        # not automatically corrupted data.
        "gap_rows": 0,
        "rejected_horizons": 0,
    }
    for row in confluence_rows or []:
        x = dict(row)
        metrics["rows"] += 1
        source_fr = x.get("forward_return_pct") or {}
        match, method, match_error = _match_forward(x, forward_rows)
        if match_error:
            metrics["lineage_conflicts"] += 1
            metrics["hard_integrity_errors"] += 1
            x["forward_evidence_source"] = "LINEAGE_CONFLICT"
            x["forward_link_method"] = None
        elif match is not None:
            source_fr = match.get("forward_return_pct") or {}
            metrics["linked_to_forward"] += 1
            if method == "EXACT_ID":
                metrics["exact_lineage_links"] += 1
            else:
                metrics["legacy_fuzzy_links"] += 1
            x["forward_evidence_source"] = "CANONICAL_FORWARD_ARCHIVE"
            x["forward_link_method"] = method
        else:
            metrics["unlinked_rows"] += 1
            x["forward_evidence_source"] = "CONFLUENCE_FALLBACK"
            x["forward_link_method"] = None

        clean, rejected = _strict_chain(source_fr)
        chain_state = _chain_state(clean, rejected)
        if chain_state == "SPARSE_SAMPLING_GAP":
            metrics["sparse_sampling_rows"] += 1
            metrics["suppressed_later_horizons"] += len(rejected)
            metrics["gap_rows"] += 1
            metrics["rejected_horizons"] += len(rejected)
        elif chain_state == "COMPLETE_24H":
            metrics["complete_24h_rows"] += 1
        else:
            metrics["awaiting_maturity_rows"] += 1

        x["forward_return_pct"] = clean
        x["maturity_integrity"] = {
            "strict_chain": True,
            "state": chain_state,
            "rejected_horizons": rejected,
            "suppressed_for_safety": bool(rejected),
            "hard_integrity_error": bool(match_error),
            "valid_through": max((h for h in HORIZONS if clean[str(h)] is not None), default=0),
        }
        out.append(x)
    return out, metrics


def _store_cloud_memory(collector, payload, forward_row):
    """Persist one cloud memory row with exact lineage and thread-safe append."""
    symbol = payload["symbol"]
    forward_id = str(forward_row.get("id") or "")
    ts = int(forward_row.get("captured_at_ms") or time.time() * 1000)

    lock = getattr(collector, "ARCHIVE_LOCK", None)
    if lock is None:
        class _Noop:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        lock = _Noop()

    with lock:
        rows = collector.read_confluence_all() if hasattr(collector, "read_confluence_all") else []
        same_symbol = [x for x in rows if x.get("symbol") == symbol]
        if forward_id and any(str(x.get("forward_observation_id") or "") == forward_id for x in same_symbol):
            return {"stored": False, "reason": "DEDUP_FORWARD_ID"}
        if same_symbol:
            latest = max(int(x.get("captured_at_ms") or 0) for x in same_symbol)
            if latest and abs(ts - latest) < MEMORY_DEDUP_MS:
                return {"stored": False, "reason": "DEDUP_45M"}

        rec = {
            "schema": "ATLAS_CONFLUENCE_MEMORY_V1",
            "captured_at": forward_row.get("captured_at") or collector.now_iso(),
            "captured_at_ms": ts,
            "symbol": symbol,
            "price": payload["price"],
            "research_only": True,
            "live_execution": False,
        }
        for key, value in payload.items():
            if key not in ("symbol", "price") and value is not None:
                rec[key] = value
        with collector.CONFLUENCE_ARCHIVE.open("a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
        return {"stored": True, "record": rec}


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
        "mirror_deduped": 0,
        "mirror_errors": 0,
        "exact_lineage_mirrors": 0,
        "skipped_non_cloud": 0,
        "skipped_deduped": 0,
        "last_error": None,
        "last_symbol": None,
        "integrity": {
            "enabled": bool(original_confluence_forward_rows),
            "rows": 0,
            "linked_to_forward": 0,
            "exact_lineage_links": 0,
            "legacy_fuzzy_links": 0,
            "unlinked_rows": 0,
            "awaiting_maturity_rows": 0,
            "complete_24h_rows": 0,
            "sparse_sampling_rows": 0,
            "suppressed_later_horizons": 0,
            "lineage_conflicts": 0,
            "hard_integrity_errors": 0,
            "gap_rows": 0,
            "rejected_horizons": 0,
        },
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

        canonical = _canonical_forward_result(result, row)
        payload = build_confluence_payload(canonical)
        if payload is None:
            state["mirror_errors"] += 1
            state["last_error"] = "invalid cloud-forward row for confluence mirror"
            return result

        state["mirror_attempts"] += 1
        state["last_symbol"] = payload["symbol"]
        try:
            memory_result = _store_cloud_memory(collector, payload, canonical)
            if isinstance(memory_result, dict) and memory_result.get("stored") is False:
                state["mirror_deduped"] += 1
            else:
                state["mirrored"] += 1
                if payload.get("forward_observation_id"):
                    state["exact_lineage_mirrors"] += 1
            state["last_error"] = None
        except Exception as exc:
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
                reconciled, metrics = reconcile_confluence_rows(raw, [])
                state["integrity"] = {"enabled": True, **metrics, "last_error": f"{type(exc).__name__}: {exc}"}
                return reconciled
        collector.confluence_forward_rows = integrity_confluence_forward_rows

    collector.forward_observe = bridged_forward_observe
    collector.RESEARCH_MEMORY_BRIDGE_STATE = state
    collector._RESEARCH_MEMORY_BRIDGE_INSTALLED = True
    return state
