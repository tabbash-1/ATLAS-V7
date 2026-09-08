"""ATLAS canonical decision truth contract.

One normalized, fail-closed view consumed by Production observability, WAIT research,
forward evaluation and the paper portfolio. It does not score, promote, execute or
change thresholds. Final Trade Guard remains the only authority for TRADE READY.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

VERSION = "ATLAS_CANONICAL_DECISION_TRUTH_V1"
PRODUCT_HORIZON = "4-12H"
EVALUATION_HORIZONS_H = (4, 8, 12)

WAIT_TAXONOMY = (
    "NO_STRUCTURE",
    "NO_CONFIRMATION",
    "POOR_RR",
    "HTF_CONFLICT",
    "LOW_VOLUME",
    "OVEREXTENDED",
    "WHALE_CONFLICT",
    "DERIVATIVES_RISK",
    "NO_CONSENSUS",
    "DATA_DEGRADED",
    "QUALITY_BLOCKED",
    "NOT_QUALIFIED",
    "OTHER",
)


def _norm(v: Any) -> str:
    return str(v or "").strip().upper()


def canonical_wait_reason(raw: Any) -> str | None:
    r = _norm(raw)
    if not r:
        return None
    if "NO_DIRECTIONAL_CONSENSUS" in r or "NO_CONSENSUS" in r:
        return "NO_CONSENSUS"
    if "HTF" in r or "DIRECTION_NOT_HTF" in r or "ACTION_NOT_HTF" in r:
        return "HTF_CONFLICT"
    if "ENTRY_CONFIRMATION" in r or "CONFIRMATION" in r:
        return "NO_CONFIRMATION"
    if "GEOMETRY" in r or "STRUCTURE" in r:
        return "NO_STRUCTURE"
    if "RR" in r or "RISK_REWARD" in r:
        return "POOR_RR"
    if "VOLUME" in r:
        return "LOW_VOLUME"
    if "OVEREXTEND" in r:
        return "OVEREXTENDED"
    if "WHALE" in r:
        return "WHALE_CONFLICT"
    if any(x in r for x in ("FUTURES", "FUNDING", "OPEN_INTEREST", "LIQUIDATION", "DERIVATIVE")):
        return "DERIVATIVES_RISK"
    if "DATA_DEGRADED" in r or "STALE" in r or "DATA_UNAVAILABLE" in r:
        return "DATA_DEGRADED"
    if "QUALITY" in r:
        return "QUALITY_BLOCKED"
    if "NOT_QUALIFIED" in r or "SCORE_BELOW_SIGNAL_THRESHOLD" in r or "PRE_FINAL_DECISION_NOT_ACTIONABLE" in r:
        return "NOT_QUALIFIED"
    return "OTHER"


def _stable_id(symbol: str, captured_at: str | None, row: dict[str, Any]) -> str:
    gate = row.get("final_trade_gate") or {}
    payload = {
        "symbol": symbol,
        "captured_at": captured_at,
        "gate_version": gate.get("version"),
        "status": gate.get("status"),
        "direction": gate.get("direction") or gate.get("product_direction"),
        "score": row.get("score"),
        "actionable_decision": row.get("actionable_decision"),
        "primary_blocker": gate.get("primary_blocker") or row.get("wait_reason"),
        "entry": ((row.get("trade_plan") or {}).get("entry")),
        "stop": ((row.get("trade_plan") or {}).get("stop_loss")),
        "tp2": ((row.get("trade_plan") or {}).get("tp2")),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def from_decision(row: dict[str, Any], symbol: str | None = None, captured_at: str | None = None) -> dict[str, Any]:
    row = row if isinstance(row, dict) else {}
    gate = row.get("final_trade_gate") or {}
    sym = str(symbol or row.get("symbol") or "UNKNOWN").upper()
    final_ready = gate.get("trade_ready") is True and _norm(gate.get("status")) == "TRADE_READY"
    direction = _norm(gate.get("direction")) if final_ready else None
    if direction not in {"LONG", "SHORT"}:
        direction = None
        final_ready = False
    raw_blocker = gate.get("primary_blocker") or row.get("wait_reason") or row.get("actionable_reason")
    canonical_reason = None if final_ready else canonical_wait_reason(raw_blocker)
    return {
        "schema": VERSION,
        "decision_id": _stable_id(sym, captured_at, row),
        "symbol": sym,
        "captured_at": captured_at,
        "product_horizon": PRODUCT_HORIZON,
        "evaluation_horizons_h": list(EVALUATION_HORIZONS_H),
        "decision": direction if final_ready else "WAIT",
        "trade_ready": final_ready,
        "paper_trade_eligible": final_ready,
        "direction": direction,
        "raw_wait_reason": None if final_ready else (str(raw_blocker) if raw_blocker else None),
        "wait_reason": canonical_reason,
        "wait_taxonomy_version": "ATLAS_WAIT_TAXONOMY_V1",
        "final_trade_gate_version": gate.get("version"),
        "source_of_truth": "FINAL_TRADE_GATE",
        "score": row.get("score"),
        "threshold": row.get("signal_threshold"),
        "analysis_only": True,
        "live_execution": False,
        "can_override_production": False,
    }


def is_trade_ready(row: dict[str, Any]) -> bool:
    return bool(from_decision(row).get("trade_ready"))
