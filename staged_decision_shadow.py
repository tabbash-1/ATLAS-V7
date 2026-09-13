"""Read-only staged decision diagnostics for ATLAS Production output.

This module never wraps production_decision, never mutates the supplied decision,
and never promotes WAIT. It only explains which evidence is currently present for
Regime -> HTF -> Flow -> 1H Trigger -> Cost/Liquidity -> Volatility/Risk.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from atlas_decision_architecture import CORE_ASSETS, PRODUCT_HORIZON, EVALUATION_HORIZONS_H, PRODUCTION_THRESHOLD
from atlas_execution_cost import evaluate_execution_cost
from atlas_risk_geometry import evaluate_risk_geometry

VERSION = "ATLAS_STAGED_DECISION_SHADOW_V1"


def _norm(v: Any) -> str:
    return str(v or "").strip().upper()


def _missing(name: str) -> Dict[str, Any]:
    return {"state": "MISSING_EVIDENCE", "available": False, "passed": False, "reason": f"{name}_EVIDENCE_MISSING"}


def _first(row: dict, *keys):
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


def _regime_layer(row: dict) -> Dict[str, Any]:
    thesis = row.get("htf_thesis") or {}
    value = _first(row, "market_regime", "regime")
    if value is None and isinstance(thesis, dict):
        value = thesis.get("market_regime") or thesis.get("regime")
    if value is None:
        return _missing("REGIME")
    state = _norm(value.get("state") if isinstance(value, dict) else value)
    return {"state": state or "UNKNOWN", "available": True, "passed": bool(state), "source": "EXPLICIT_PRODUCTION_EVIDENCE"}


def _htf_layer(row: dict) -> Dict[str, Any]:
    gate = row.get("final_trade_gate") or {}
    thesis = row.get("htf_thesis") or {}
    product = _norm(gate.get("product_direction") or row.get("product_direction") or (thesis.get("product_direction") if isinstance(thesis, dict) else None))
    alignment = _norm(gate.get("direction_alignment") or row.get("direction_alignment") or (thesis.get("direction_alignment") if isinstance(thesis, dict) else None))
    if product not in {"LONG", "SHORT"}:
        return _missing("HTF_DIRECTION")
    passed = alignment == "ALIGNED"
    return {"state": product, "available": True, "passed": passed, "alignment": alignment or None, "source": "FINAL_TRADE_GATE_HTF_EVIDENCE"}


def _flow_layer(row: dict) -> Dict[str, Any]:
    value = _first(row, "flow_confirmation", "order_flow", "market_flow", "flow_state")
    if value is None:
        return _missing("FLOW")
    if isinstance(value, dict):
        state = _norm(value.get("state") or value.get("direction") or value.get("bias") or value.get("status"))
        freshness_ok = value.get("freshness_ok", True) is not False and value.get("stale", False) is not True
    else:
        state = _norm(value)
        freshness_ok = True
    passed = state in {"LONG", "SHORT", "BULLISH", "BEARISH", "ALIGNED", "CONFIRMED", "PASS"} and freshness_ok
    return {"state": state or "UNKNOWN", "available": True, "passed": passed, "freshness_ok": freshness_ok, "source": "EXPLICIT_PRODUCTION_EVIDENCE"}


def _trigger_layer(row: dict) -> Dict[str, Any]:
    gate = row.get("final_trade_gate") or {}
    product = _norm(gate.get("product_direction") or row.get("product_direction"))
    entry = _norm(gate.get("entry_confirmation_direction") or row.get("entry_confirmation_direction"))
    if entry not in {"LONG", "SHORT"}:
        return _missing("TRIGGER_1H")
    passed = product in {"LONG", "SHORT"} and entry == product
    return {"state": entry, "available": True, "passed": passed, "product_direction": product or None, "source": "FINAL_TRADE_GATE_ENTRY_CONFIRMATION"}


def _cost_layer(row: dict) -> Dict[str, Any]:
    expected = row.get("expected_move_bps")
    costs = row.get("execution_costs") or row.get("cost_model") or {}
    if expected is None or not isinstance(costs, dict):
        return _missing("COST_LIQUIDITY")
    required = ("fee_bps", "spread_bps", "slippage_bps")
    if any(costs.get(k) is None for k in required):
        return _missing("COST_LIQUIDITY")
    try:
        result = evaluate_execution_cost(
            expected_move_bps=float(expected),
            fee_bps=float(costs["fee_bps"]),
            spread_bps=float(costs["spread_bps"]),
            slippage_bps=float(costs["slippage_bps"]),
            funding_bps=float(costs.get("funding_bps") or 0.0),
            safety_multiplier=float(costs.get("safety_multiplier") or 1.25),
        )
    except (TypeError, ValueError) as exc:
        return {"state": "INVALID_EVIDENCE", "available": True, "passed": False, "reason": str(exc)}
    return {
        "state": result.reason, "available": True, "passed": result.passed,
        "expected_move_bps": result.expected_move_bps, "modeled_cost_bps": result.modeled_cost_bps,
        "required_edge_bps": result.required_edge_bps, "net_edge_bps": result.net_edge_bps,
        "source": "EXPLICIT_PRODUCTION_COST_EVIDENCE",
    }


def _risk_layer(row: dict) -> Dict[str, Any]:
    direction = _norm(row.get("candidate_direction") or (row.get("final_trade_gate") or {}).get("product_direction"))
    entry = row.get("entry")
    stop = row.get("stop_loss")
    tp1 = row.get("tp1")
    tp2 = row.get("tp2") or row.get("take_profit")
    if direction not in {"LONG", "SHORT"} or None in (entry, stop, tp1, tp2):
        return _missing("VOLATILITY_RISK")
    try:
        result = evaluate_risk_geometry(direction=direction, entry=float(entry), stop=float(stop), tp1=float(tp1), tp2=float(tp2))
    except (TypeError, ValueError) as exc:
        return {"state": "INVALID_EVIDENCE", "available": True, "passed": False, "reason": str(exc)}
    return {
        "state": result.reason, "available": True, "passed": result.geometry_valid,
        "rr_tp1": result.rr_tp1, "rr_tp2": result.rr_tp2, "risk_per_unit": result.risk_per_unit,
        "source": "EXACT_DECISION_GEOMETRY",
    }


def build_shadow(decision: dict, symbol: str | None = None) -> Dict[str, Any]:
    """Build diagnostics without mutating or overriding the canonical decision."""
    row = deepcopy(decision if isinstance(decision, dict) else {})
    symbol = _norm(symbol or row.get("symbol"))
    if symbol not in CORE_ASSETS:
        return {
            "ok": False, "error": "unsupported canonical symbol", "symbol": symbol or None,
            "supported_symbols": list(CORE_ASSETS), "shadow_only": True, "research_only": True,
            "can_override_production": False, "live_execution": False,
        }
    canonical = deepcopy(row.get("canonical_decision") or {})
    layers = {
        "regime": _regime_layer(row),
        "htf_direction": _htf_layer(row),
        "flow_confirmation": _flow_layer(row),
        "trigger_1h": _trigger_layer(row),
        "cost_liquidity": _cost_layer(row),
        "volatility_risk": _risk_layer(row),
    }
    missing = [name for name, layer in layers.items() if not layer.get("available")]
    failed = [name for name, layer in layers.items() if layer.get("available") and not layer.get("passed")]
    return {
        "ok": True,
        "version": VERSION,
        "symbol": symbol,
        "product_horizon": PRODUCT_HORIZON,
        "evaluation_horizons_h": list(EVALUATION_HORIZONS_H),
        "production_threshold": PRODUCTION_THRESHOLD,
        "canonical_decision": canonical,
        "canonical_decision_unchanged": True,
        "final_trade_gate_unchanged": True,
        "layers": layers,
        "missing_evidence": missing,
        "failed_layers": failed,
        "shadow_ready": not missing and not failed,
        "shadow_only": True,
        "research_only": True,
        "can_override_production": False,
        "live_execution": False,
    }
