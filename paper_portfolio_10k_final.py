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
    if gate.get("production_signal_qualified") is not True or gate.get("canonical_geometry_ready") is not True:
        return False
    if str(gate.get("direction_alignment") or "").upper() != "ALIGNED":
        return False
    g = portfolio.geometry(decision)
    return bool(g and g.get("direction") == action)


portfolio.trade_ready = strict_trade_ready

if __name__ == "__main__":
    portfolio.main()
