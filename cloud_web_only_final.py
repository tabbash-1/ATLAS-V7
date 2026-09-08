#!/usr/bin/env python3
"""Render entrypoint that installs the final ATLAS trade-ready guard last."""
from __future__ import annotations
import os
import runpy
import urllib.parse
from pathlib import Path

BASE = Path(__file__).resolve().parent
ns = runpy.run_path(str(BASE / "cloud_web_only.py"), run_name="atlas_cloud_web_only_base")
atlas = ns["atlas"]
from final_trade_ready_guard import install as install_final_trade_ready_guard
FINAL_TRADE_READY_GUARD = install_final_trade_ready_guard(atlas)
if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):
    atlas.WEB_SAFE_MODE["final_trade_ready_guard"] = FINAL_TRADE_READY_GUARD

from whale_intelligence import VERSION as WHALE_INTELLIGENCE_VERSION
from whale_intelligence import filter_feed as filter_whale_feed
from whale_intelligence import load_snapshot as load_whale_snapshot
from canonical_outcome_snapshot import VERSION as CANONICAL_OUTCOME_VERSION
from canonical_outcome_snapshot import load_snapshot as load_canonical_outcomes


def _whale_snapshot():
    return load_whale_snapshot(BASE)


def _outcome_snapshot():
    # Web process is read-only: scheduled GitHub Actions own generation/settlement.
    return load_canonical_outcomes(BASE)


def _outcome_rows(snapshot, symbol=None):
    rows = list(((snapshot.get("signals") or {}).get("rows") or []))
    if symbol:
        symbol = str(symbol).upper()
        rows = [x for x in rows if str(x.get("symbol") or "").upper() == symbol]
    return rows


class FinalWebOnlyHandler(ns["WebOnlyHandler"]):
    """Web-only handler with explicit final-decision, outcome and whale contracts."""
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/runtime/status":
            whale = _whale_snapshot()
            outcomes = _outcome_snapshot()
            return self._json({
                "ok": True,
                "service": "ATLAS_V7",
                "runtime": "WEB_ONLY_FINAL",
                "web_safe_mode": atlas.WEB_SAFE_MODE,
                "final_trade_ready_guard": FINAL_TRADE_READY_GUARD,
                "production_threshold": float(atlas.CLOUD_FORWARD_MIN_SCORE),
                "product_horizon": "4-12H",
                "canonical_outcomes": {
                    "version": CANONICAL_OUTCOME_VERSION,
                    "state": outcomes.get("state", "READY"),
                    "decision_source_of_truth": outcomes.get("decision_source_of_truth"),
                    "evaluation_horizons_h": outcomes.get("evaluation_horizons_h"),
                    "signal_count": (outcomes.get("signals") or {}).get("count", 0),
                    "web_process_background_worker": False,
                },
                "whale_intelligence": {
                    "version": WHALE_INTELLIGENCE_VERSION,
                    "state": whale.get("state"),
                    "data_available": whale.get("data_available"),
                    "provider": whale.get("provider"),
                    "last_updated": whale.get("last_updated"),
                },
                "research_only": True,
                "analysis_only": True,
                "live_execution": False,
            })
        if parsed.path in {
            "/api/outcomes/ledger", "/api/outcomes/summary",
            "/api/outcomes/path-ledger", "/api/outcomes/path-summary",
            "/api/outcomes/geometry-status", "/api/outcomes/settlement-status",
        }:
            q = urllib.parse.parse_qs(parsed.query)
            scope = str((q.get("scope") or ["signals"])[0]).lower()
            if scope not in {"signals", "execution"}:
                return self._json({"error":"Production web exposes only canonical signals/execution scopes","scope":scope,"research_only":True,"live_execution":False}, 400)
            snapshot = _outcome_snapshot()
            symbol = (q.get("symbol") or [None])[0]
            horizon_raw = (q.get("horizon") or ["12"])[0]
            try:
                horizon = int(horizon_raw)
            except Exception:
                horizon = -1
            if horizon not in (4, 8, 12):
                return self._json({"error":"official outcome horizon must be one of 4, 8, 12","research_only":True,"live_execution":False}, 400)
            rows = _outcome_rows(snapshot, symbol=symbol)
            base = {
                "schema": snapshot.get("schema"),
                "state": snapshot.get("state", "READY"),
                "decision_source_of_truth": snapshot.get("decision_source_of_truth"),
                "product_horizon": snapshot.get("product_horizon"),
                "evaluation_horizons_h": snapshot.get("evaluation_horizons_h"),
                "legacy_backfill_allowed": False,
                "scope": scope,
                "symbol": symbol,
                "horizon_h": horizon,
                "served_from": "COMMITTED_GITHUB_ACTIONS_SNAPSHOT",
                "web_process_background_worker": False,
                "outcome_read_triggered_by_request": False,
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            }
            if parsed.path == "/api/outcomes/ledger":
                return self._json({**base, "rows": rows, "count": len(rows)})
            if parsed.path == "/api/outcomes/summary":
                return self._json({**base, "summary": snapshot.get("summary") or {}, "signal_count": len(rows)})
            if parsed.path == "/api/outcomes/path-ledger":
                return self._json({**base, "rows": rows, "count": len(rows), "path_semantics":"CANONICAL_PAPER_TRADE_PATH_ONLY"})
            if parsed.path == "/api/outcomes/path-summary":
                return self._json({**base, "path_summary": snapshot.get("path_summary") or {}, "path_semantics":"CANONICAL_PAPER_TRADE_PATH_ONLY"})
            if parsed.path == "/api/outcomes/geometry-status":
                return self._json({**base, "geometry_status": snapshot.get("geometry_status") or {}})
            return self._json({**base, "settlement_status": snapshot.get("settlement_status") or {}})
        if parsed.path == "/api/whales/status":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "version": whale.get("version"),
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "provider": whale.get("provider"),
                "provider_authenticated": whale.get("provider_authenticated"),
                "last_updated": whale.get("last_updated"),
                "snapshot_age_minutes": whale.get("snapshot_age_minutes"),
                "stale_after_minutes": whale.get("stale_after_minutes"),
                "rejected_rows": whale.get("rejected_rows"),
                "rejection_reasons": whale.get("rejection_reasons"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/top10":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "count": len(whale.get("top10") or []),
                "top10": whale.get("top10") or [],
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/feed":
            q = urllib.parse.parse_qs(parsed.query)
            whale = _whale_snapshot()
            rows = filter_whale_feed(
                whale,
                asset=(q.get("asset") or [None])[0],
                flow_type=(q.get("flow_type") or [None])[0],
                bias=(q.get("bias") or [None])[0],
            )
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "count": len(rows),
                "feed": rows,
                "filters": {
                    "asset": (q.get("asset") or [None])[0],
                    "flow_type": (q.get("flow_type") or [None])[0],
                    "bias": (q.get("bias") or [None])[0],
                },
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        if parsed.path == "/api/whales/consensus":
            whale = _whale_snapshot()
            return self._json({
                "ok": True,
                "state": whale.get("state"),
                "data_available": whale.get("data_available"),
                "consensus": whale.get("consensus"),
                "source": whale.get("provider"),
                "last_updated": whale.get("last_updated"),
                "message": whale.get("message"),
                "research_only": True,
                "live_execution": False,
                "can_override_production": False,
            })
        return super().do_GET()


if __name__ == "__main__":
    os.chdir(atlas.ROOT)
    port = int(os.environ.get("PORT", "8080"))
    print("ATLAS Render WEB-ONLY safe mode + FINAL TRADE READY guard", flush=True)
    print(f"Final trade-ready guard: {FINAL_TRADE_READY_GUARD['version']}", flush=True)
    print(f"Canonical outcomes: {CANONICAL_OUTCOME_VERSION}", flush=True)
    print(f"Whale intelligence: {WHALE_INTELLIGENCE_VERSION}", flush=True)
    print(f"Listening on {port}", flush=True)
    ns["Server"](("0.0.0.0", port), FinalWebOnlyHandler).serve_forever(poll_interval=0.5)
