"""Cached audit of ATLAS persistent Forward + Smart-Money history.

This layer is deliberately outcome-free. It answers one question: how much of
ATLAS's older persistent history can be used as decision-time input for an
honest retrospective replay? It never reads forward returns, settlement files,
or future smart-money snapshots.
"""
from __future__ import annotations

import bisect
import copy
import threading
import time
import urllib.parse
from collections import Counter, defaultdict

import historical_evaluation_protocol
import historical_replay_registry

VERSION = "ATLAS_HISTORICAL_SOURCE_AUDIT_V1_PRIOR_ONLY_CACHED"
MAX_SMART_AGE_MS = 2 * 60 * 60 * 1000
REFRESH_SECONDS = 900

STATE = {
    "enabled": True,
    "background_only": True,
    "cached_only": True,
    "research_only": True,
    "live_execution": False,
    "refreshes": 0,
    "last_error": None,
    "last_started_at": None,
    "last_finished_at": None,
    "report": None,
}

FORWARD_FIELDS = (
    "id", "captured_at", "captured_at_ms", "symbol", "direction", "entry",
    "champion_score", "challenger_score", "final_score", "opportunity_score",
    "playbook_primary", "playbook_score", "regime", "relative_volume",
    "volume_quality", "relative_strength_score", "futures_available",
    "futures_provider", "futures_score", "rr_tp1", "rr_tp2",
    "execution_decision", "trade_plan_status", "research_sampling_lane",
    "auto_source", "signal_threshold_at_entry", "research_threshold_at_entry",
)

SMART_FIELDS = (
    "captured_at", "captured_at_ms", "symbol", "mark_price", "funding_rate",
    "open_interest", "oi_change_pct", "taker_ratio", "taker_buy_vol",
    "taker_sell_vol", "orderbook_bid_notional_top20",
    "orderbook_ask_notional_top20", "orderbook_imbalance",
    "price_change_24h_pct", "quote_volume_24h", "futures_provider",
    "futures_evidence_validated",
)

MICRO_REQUIRED = (
    "funding_rate", "open_interest", "taker_ratio", "orderbook_imbalance",
)


def _ts(row):
    try:
        return int(row.get("captured_at_ms") or 0)
    except Exception:
        return 0


def _present(row, key):
    return key in row and row.get(key) is not None and row.get(key) != ""


def _sanitized(row, allowed):
    return {k: row.get(k) for k in allowed if k in row}


def _iso_ms(ms, atlas):
    if not ms:
        return None
    try:
        import datetime as dt
        return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat()
    except Exception:
        return None


def build_report(atlas, max_smart_age_ms=MAX_SMART_AGE_MS):
    raw_forward = atlas.read_forward()
    raw_smart = atlas.read_all()
    forward = [_sanitized(r, FORWARD_FIELDS) for r in raw_forward if isinstance(r, dict)]
    smart = [_sanitized(r, SMART_FIELDS) for r in raw_smart if isinstance(r, dict)]

    fwd_valid = [r for r in forward if _ts(r) > 0 and r.get("symbol") and r.get("direction") in ("LONG", "SHORT") and r.get("entry") is not None]
    sm_valid = [r for r in smart if _ts(r) > 0 and r.get("symbol")]

    by_symbol = defaultdict(list)
    for r in sm_valid:
        by_symbol[r["symbol"]].append(r)
    smart_times = {}
    for symbol in by_symbol:
        by_symbol[symbol].sort(key=_ts)
        smart_times[symbol] = [_ts(x) for x in by_symbol[symbol]]

    matched = 0
    matched_validated = 0
    micro_complete = 0
    age_buckets = Counter()
    provider_counts = Counter()
    per_symbol = defaultdict(lambda: {"forward": 0, "prior_smart_match": 0, "validated_prior_smart": 0, "micro_complete": 0})
    forward_field_counts = Counter()
    smart_field_counts = Counter()

    for r in fwd_valid:
        symbol = r["symbol"]
        per_symbol[symbol]["forward"] += 1
        for key in FORWARD_FIELDS:
            if _present(r, key):
                forward_field_counts[key] += 1
        rows = by_symbol.get(symbol) or []
        times = smart_times.get(symbol) or []
        if not rows:
            continue
        t = _ts(r)
        i = bisect.bisect_right(times, t) - 1
        if i < 0:
            continue
        sm = rows[i]
        age = t - _ts(sm)
        if age < 0 or age > max_smart_age_ms:
            continue
        matched += 1
        per_symbol[symbol]["prior_smart_match"] += 1
        if age <= 30 * 60 * 1000:
            age_buckets["LE_30M"] += 1
        elif age <= 60 * 60 * 1000:
            age_buckets["31_60M"] += 1
        else:
            age_buckets["61_120M"] += 1
        provider = sm.get("futures_provider") or "UNKNOWN"
        provider_counts[provider] += 1
        for key in SMART_FIELDS:
            if _present(sm, key):
                smart_field_counts[key] += 1
        if sm.get("futures_evidence_validated") is True:
            matched_validated += 1
            per_symbol[symbol]["validated_prior_smart"] += 1
        if all(_present(sm, k) for k in MICRO_REQUIRED):
            micro_complete += 1
            per_symbol[symbol]["micro_complete"] += 1

    fwd_times = [_ts(r) for r in fwd_valid]
    sm_times = [_ts(r) for r in sm_valid]
    n = len(fwd_valid)
    return {
        "schema": VERSION,
        "generated_at": atlas.now_iso(),
        "research_only": True,
        "live_execution": False,
        "outcomes_read": False,
        "forward_return_fields_read": False,
        "settlement_files_read": False,
        "backfill_performed": False,
        "future_smart_money_match_allowed": False,
        "smart_money_match_policy": "LATEST_SAME_SYMBOL_SNAPSHOT_AT_OR_BEFORE_FORWARD_TIMESTAMP",
        "max_smart_money_age_minutes": round(max_smart_age_ms / 60000),
        "forward": {
            "raw_rows": len(raw_forward),
            "usable_decision_time_rows": n,
            "first_at": _iso_ms(min(fwd_times), atlas) if fwd_times else None,
            "last_at": _iso_ms(max(fwd_times), atlas) if fwd_times else None,
            "field_coverage": {k: {"rows": forward_field_counts[k], "pct": round(100 * forward_field_counts[k] / n, 2) if n else 0.0} for k in FORWARD_FIELDS},
        },
        "smart_money": {
            "raw_rows": len(raw_smart),
            "usable_timestamped_rows": len(sm_valid),
            "first_at": _iso_ms(min(sm_times), atlas) if sm_times else None,
            "last_at": _iso_ms(max(sm_times), atlas) if sm_times else None,
        },
        "prior_context_join": {
            "matched_forward_rows": matched,
            "match_pct": round(100 * matched / n, 2) if n else 0.0,
            "validated_futures_context_rows": matched_validated,
            "validated_pct_of_matched": round(100 * matched_validated / matched, 2) if matched else 0.0,
            "microstructure_complete_rows": micro_complete,
            "microstructure_complete_pct_of_matched": round(100 * micro_complete / matched, 2) if matched else 0.0,
            "age_buckets": dict(age_buckets),
            "provider_counts": dict(provider_counts),
            "matched_smart_field_coverage": {k: {"rows": smart_field_counts[k], "pct": round(100 * smart_field_counts[k] / matched, 2) if matched else 0.0} for k in SMART_FIELDS},
        },
        "per_symbol": dict(sorted(per_symbol.items())),
        "replay_classification": {
            "historical_backtest_possible": bool(n >= 100),
            "microstructure_replay_possible": bool(micro_complete >= 60),
            "forward_proof_equivalent": False,
            "note": "Recorded prior-only inputs can accelerate retrospective model discovery, but they do not replace the live frozen forward cohort for final validation.",
        },
    }


def refresh(atlas):
    STATE["last_started_at"] = atlas.now_iso()
    try:
        STATE["report"] = build_report(atlas)
        STATE["refreshes"] += 1
        STATE["last_error"] = None
    except Exception as exc:
        STATE["last_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        STATE["last_finished_at"] = atlas.now_iso()
    return copy.deepcopy(STATE)


def install(atlas):
    atlas.HISTORICAL_SOURCE_AUDIT_STATE = STATE
    original = atlas.Handler.do_GET

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/research/historical-source-audit":
            registry = getattr(atlas, 'HISTORICAL_REPLAY_REGISTRY_STATE', {}) or {}
            protocol = getattr(atlas, 'HISTORICAL_EVALUATION_PROTOCOL_STATE', {}) or {}
            return self._json({
                "ok": STATE.get("report") is not None,
                "version": VERSION,
                "cached_only": True,
                "background_refresh_triggered": False,
                "research_only": True,
                "live_execution": False,
                "outcomes_read_by_request": False,
                "runtime": {k: STATE.get(k) for k in ("enabled", "background_only", "refreshes", "last_error", "last_started_at", "last_finished_at")},
                "replay_registry": {k: registry.get(k) for k in ("status", "registration_locked", "frozen_feature_rows", "feature_dataset_sha256", "last_error", "last_checked_at")},
                "evaluation_protocol": {k: protocol.get(k) for k in ("status", "registration_locked", "protocol_hash", "feature_dataset_sha256", "last_error")},
                "report": copy.deepcopy(STATE.get("report")),
            })
        return original(self)

    atlas.Handler.do_GET = do_GET

    def loop():
        time.sleep(10)
        while True:
            refresh(atlas)
            time.sleep(REFRESH_SECONDS)

    threading.Thread(target=loop, daemon=True, name="atlas-historical-source-audit").start()
    try:
        historical_replay_registry.install(atlas)
        # Preregister only after the replay registry has frozen and locked its
        # feature dataset. This module contains no outcome reader.
        historical_evaluation_protocol.install(atlas)
    except Exception as exc:
        STATE['last_error'] = f"HISTORICAL_REPLAY_GOVERNANCE_INSTALL_ERROR: {type(exc).__name__}: {exc}"
    return STATE
