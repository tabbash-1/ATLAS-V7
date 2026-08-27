"""Canonical Production opportunity scan and qualified paper-trade recorder.

This layer never scores a setup itself.  It calls ``atlas.production_decision``
for every supported asset and exposes one execution vocabulary:

* ENTER_LONG / ENTER_SHORT: Production ACTIONABLE now.
* WAIT: ARMED, WATCH, NO_SETUP, unavailable, or errored.

Only ACTIONABLE decisions with complete, valid geometry are written to the
paper-trade archive.  ARMED conditional plans remain visible but are never
recorded as entries before their trigger is re-evaluated by Production.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


VERSION = "PRODUCTION_OPPORTUNITY_RUNTIME_V1"
DEDUPE_MINUTES = 50
_LOCK = threading.RLock()
SNAPSHOT_MAX_AGE_MINUTES = 90


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _execution_action(decision):
    state = str((decision or {}).get("opportunity_state") or "NO_SETUP").upper()
    direction = str((decision or {}).get("candidate_direction") or "").upper()
    plan = (decision or {}).get("trade_plan") or {}
    ready = bool((decision or {}).get("execution_ready"))
    qualified = bool((decision or {}).get("production_signal_qualified"))
    geometry_valid = bool(((decision or {}).get("geometry_gate") or {}).get("qualified"))
    complete = all(_num(plan.get(key)) is not None for key in ("entry", "stop_loss", "tp1", "tp2", "rr_tp2"))
    if state == "ACTIONABLE" and ready and qualified and geometry_valid and complete and direction in ("LONG", "SHORT"):
        return f"ENTER_{direction}"
    return "WAIT"


def normalize(decision, symbol=None):
    decision = decision if isinstance(decision, dict) else {}
    plan = decision.get("trade_plan") or {}
    action = _execution_action(decision)
    return {
        "symbol": decision.get("symbol") or symbol,
        "action": action,
        "opportunity_state": decision.get("opportunity_state") or "NO_SETUP",
        "direction": decision.get("candidate_direction"),
        "score": _num(decision.get("score")),
        "threshold": _num(decision.get("signal_threshold")),
        "entry_mode": plan.get("entry_mode"),
        "entry": _num(plan.get("entry")),
        "entry_trigger": plan.get("entry_trigger"),
        "stop_loss": _num(plan.get("stop_loss")),
        "tp1": _num(plan.get("tp1")),
        "tp2": _num(plan.get("tp2")),
        "rr_tp1": _num(plan.get("rr_tp1")),
        "rr_tp2": _num(plan.get("rr_tp2")),
        "reason": decision.get("actionable_reason") or decision.get("wait_reason") or decision.get("opportunity_state_reason"),
        "production_signal_qualified": bool(decision.get("production_signal_qualified")),
        "geometry_valid": bool((decision.get("geometry_gate") or {}).get("qualified")),
        "execution_ready": bool(decision.get("execution_ready")),
        "decision_engine_version": decision.get("decision_engine_version") or decision.get("source"),
        "trade_plan_version": plan.get("version"),
        "generated_at": decision.get("generated_at"),
        "research_only": True,
        "live_execution": False,
    }


def _read(path):
    rows = []
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def _store_actionable(atlas, decision):
    row = normalize(decision)
    if row["action"] not in ("ENTER_LONG", "ENTER_SHORT"):
        return {"stored": False, "reason": "NOT_ACTIONABLE"}
    path = Path(atlas.DATA) / "production_paper_trades.jsonl"
    now_ms = int(time.time() * 1000)
    with _LOCK:
        for old in reversed(_read(path)[-500:]):
            if old.get("symbol") == row["symbol"] and old.get("direction") == row["direction"]:
                age = now_ms - int(old.get("captured_at_ms") or 0)
                if age < DEDUPE_MINUTES * 60 * 1000:
                    return {"stored": False, "reason": "DEDUP_WINDOW", "record": old}
                break
        record = {
            "schema": "ATLAS_PRODUCTION_PAPER_TRADE_V1",
            "id": f"prod-{row['symbol']}-{row['direction']}-{now_ms}",
            "captured_at": atlas.now_iso(),
            "captured_at_ms": now_ms,
            **row,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

        # Mirror the qualified entry into the existing frozen-geometry outcome
        # pipeline so its TP/SL path can mature automatically.
        payload = {
            "symbol": row["symbol"], "direction": row["direction"], "entry": row["entry"],
            "final_score": row["score"], "champion_score": row["score"],
            "signal_threshold": row["threshold"], "production_signal_qualified": True,
            "execution_ready": True, "opportunity_state": "ACTIONABLE",
            "execution_decision": row["action"], "trade_plan_status": "ACTIONABLE",
            "stop_loss": row["stop_loss"], "tp1": row["tp1"], "tp2": row["tp2"],
            "rr_tp1": row["rr_tp1"], "rr_tp2": row["rr_tp2"],
            "auto_source": VERSION, "dedup_minutes": DEDUPE_MINUTES,
        }
        try:
            record["outcome_observation"] = atlas.forward_observe(payload)
        except Exception as exc:
            record["outcome_observation_error"] = f"{type(exc).__name__}: {exc}"
        return {"stored": True, "record": record}


def scan(atlas, store=False):
    symbols = list(dict.fromkeys(atlas.ON_DEMAND_SYMBOLS))
    decisions = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=min(4, len(symbols) or 1)) as pool:
        futures = {pool.submit(atlas.production_decision, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                decision = future.result()
                if not isinstance(decision, dict) or not decision.get("ok"):
                    raise RuntimeError((decision or {}).get("error") or "Production decision unavailable")
                decisions[symbol] = decision
            except Exception as exc:
                errors[symbol] = f"{type(exc).__name__}: {exc}"

    rows = [normalize(decisions[symbol], symbol) for symbol in symbols if symbol in decisions]
    for symbol, error in errors.items():
        rows.append({"symbol": symbol, "action": "WAIT", "opportunity_state": "UNAVAILABLE", "reason": error,
                     "production_signal_qualified": False, "geometry_valid": False, "execution_ready": False,
                     "research_only": True, "live_execution": False})
    order = {"ENTER_LONG": 0, "ENTER_SHORT": 0, "WAIT": 1}
    state_order = {"ACTIONABLE": 0, "ARMED": 1, "WATCH": 2, "NO_SETUP": 3, "UNAVAILABLE": 4}
    rows.sort(key=lambda row: (order.get(row.get("action"), 9), state_order.get(row.get("opportunity_state"), 9), -(_num(row.get("score")) or -1)))

    stored = []
    if store:
        for symbol, decision in decisions.items():
            result = _store_actionable(atlas, decision)
            if result.get("stored"):
                stored.append(result["record"])
    return {
        "ok": True, "version": VERSION, "generated_at": atlas.now_iso(), "rows": rows,
        "summary": {
            "assets": len(rows),
            "actionable": sum(row.get("action") in ("ENTER_LONG", "ENTER_SHORT") for row in rows),
            "armed": sum(row.get("opportunity_state") == "ARMED" for row in rows),
            "wait": sum(row.get("action") == "WAIT" for row in rows),
            "errors": len(errors),
            "paper_trades_stored": len(stored),
        },
        "single_source_of_truth": "atlas.production_decision",
        "fallback_signals_allowed": False,
        "research_only": True,
        "live_execution": False,
    }


def _snapshot_report(atlas):
    path = Path(atlas.ROOT) / "status" / "atlas-production-latest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        captured_at = payload.get("captured_at")
        captured = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
        age_minutes = max(0.0, (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds() / 60)
        stale = age_minutes > SNAPSHOT_MAX_AGE_MINUTES
        decisions = payload.get("decisions") or {}
        rows = [normalize(decisions[symbol], symbol) for symbol in atlas.ON_DEMAND_SYMBOLS if symbol in decisions]
        if stale:
            for row in rows:
                row.update({
                    "action": "WAIT", "opportunity_state": "STALE", "execution_ready": False,
                    "reason": f"PRODUCTION_SNAPSHOT_STALE_{round(age_minutes, 1)}M",
                })
        return {
            "ok": True, "version": VERSION, "generated_at": captured_at, "rows": rows,
            "summary": {
                "assets": len(rows),
                "actionable": sum(row.get("action") in ("ENTER_LONG", "ENTER_SHORT") for row in rows),
                "armed": sum(row.get("opportunity_state") == "ARMED" for row in rows),
                "wait": sum(row.get("action") == "WAIT" for row in rows),
                "errors": 0, "paper_trades_stored": 0,
            },
            "source": "CACHED_PRODUCTION_SNAPSHOT", "snapshot_age_minutes": round(age_minutes, 2),
            "snapshot_stale": stale, "refreshing": False,
            "single_source_of_truth": "atlas.production_decision", "fallback_signals_allowed": False,
            "research_only": True, "live_execution": False,
        }
    except Exception:
        return None


def install(atlas):
    if getattr(atlas, "_PRODUCTION_OPPORTUNITY_RUNTIME_INSTALLED", False):
        return atlas.PRODUCTION_OPPORTUNITY_RUNTIME_STATE
    original_get = atlas.Handler.do_GET
    original_cycle = atlas.cloud_forward_cycle
    state = {"enabled": True, "version": VERSION, "cycles": 0, "last_scan_at": None, "last_error": None,
             "refreshing": False, "cached_report": _snapshot_report(atlas)}
    refresh_lock = threading.Lock()

    def refresh_cache(store=False):
        if not refresh_lock.acquire(blocking=False):
            return
        state["refreshing"] = True
        try:
            report = scan(atlas, store=store)
            report.update({"source": "LIVE_PRODUCTION_SCAN", "snapshot_age_minutes": 0,
                           "snapshot_stale": False, "refreshing": False})
            state["cached_report"] = report
            state["cycles"] += 1
            state["last_scan_at"] = report.get("generated_at")
            state["last_summary"] = report.get("summary")
            state["last_error"] = None
        except Exception as exc:
            state["last_error"] = f"{type(exc).__name__}: {exc}"
        finally:
            state["refreshing"] = False
            refresh_lock.release()

    def production_cycle():
        result = original_cycle()
        refresh_cache(store=True)
        return result

    def do_get(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/production/opportunities":
            try:
                cached = state.get("cached_report") or _snapshot_report(atlas)
                if not state.get("refreshing"):
                    threading.Thread(target=refresh_cache, kwargs={"store": True}, daemon=True,
                                     name="atlas-production-scan-refresh").start()
                if cached:
                    response = dict(cached)
                    response["refreshing"] = True
                    response["last_refresh_error"] = state.get("last_error")
                    return self._json(response, 200)
                return self._json({
                    "ok": True, "version": VERSION, "generated_at": atlas.now_iso(), "rows": [],
                    "summary": {"assets": 0, "actionable": 0, "armed": 0, "wait": 0, "errors": 0, "paper_trades_stored": 0},
                    "source": "PRODUCTION_WARMING", "snapshot_stale": True, "refreshing": True,
                    "single_source_of_truth": "atlas.production_decision", "fallback_signals_allowed": False,
                    "research_only": True, "live_execution": False,
                }, 200)
            except Exception as exc:
                return self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}", "version": VERSION,
                                   "research_only": True, "live_execution": False}, 500)
        if u.path == "/api/production/paper-trades":
            q = urllib.parse.parse_qs(u.query)
            limit = max(1, min(500, int(q.get("limit", ["100"])[0])))
            rows = list(reversed(_read(Path(atlas.DATA) / "production_paper_trades.jsonl")[-limit:]))
            return self._json({"ok": True, "version": VERSION, "rows": rows, "count": len(rows),
                               "research_only": True, "live_execution": False}, 200)
        return original_get(self)

    atlas.cloud_forward_cycle = production_cycle
    atlas.production_opportunity_scan = lambda store=False: scan(atlas, store=store)
    atlas.Handler.do_GET = do_get
    atlas.PRODUCTION_OPPORTUNITY_RUNTIME_STATE = state
    atlas._PRODUCTION_OPPORTUNITY_RUNTIME_INSTALLED = True
    return state
