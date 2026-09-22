#!/usr/bin/env python3
"""Strict entrypoint for the ATLAS $10K paper portfolio.

The legacy portfolio engine remains intact for settlement/accounting. This
wrapper replaces only its enrollment predicate: a snapshot is eligible solely
when the final 4-12H guard explicitly certified TRADE_READY.
"""
from __future__ import annotations
import paper_portfolio_10k as portfolio

VERSION = "PAPER_PORTFOLIO_FINAL_GATE_V1"


def strict_trade_ready(decision):
    if not isinstance(decision, dict):
        return False
    gate = decision.get("final_trade_gate") or {}
    action = str(decision.get("actionable_decision") or "").upper()
    direction = str(gate.get("direction") or "").upper()
    if decision.get("trade_ready") is not True:
        return False
    if gate.get("trade_ready") is not True or str(gate.get("status") or "").upper() != "TRADE_READY":
        return False
    if action not in {"LONG", "SHORT"} or direction != action:
        return False
    if gate.get("canonical_geometry_ready") is not True:
        return False
    if str(gate.get("direction_alignment") or "").upper() not in {"ALIGNED", "CONDITIONAL_ALIGNED", "CONDITIONAL_ALIGNED_12H_NEUTRAL"}:
        return False
    trader = gate.get("trader_brain") or {}
    if trader.get("stage") != "TRADE_READY" or trader.get("score_is_authority") is not False:
        return False
    rr = trader.get("rr_tp2")
    try:
        if rr is None or float(rr) < 2.0:
            return False
    except (TypeError, ValueError):
        return False
    g = portfolio.geometry(decision)
    return bool(g and g.get("direction") == action)


def install_strict_guard():
    """Install the strict predicate only for the executable wrapper.

    Importing this module for tests or diagnostics must not mutate the shared
    legacy accounting module for the rest of the Python process.
    """
    portfolio.trade_ready = strict_trade_ready

if __name__ == "__main__":
    install_strict_guard()
    portfolio.main()
