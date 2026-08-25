#!/usr/bin/env python3
"""ATLAS Whale-10 Consensus research layer.

This module intentionally refuses to manufacture a whale signal from top-holder
balances or exchange/custody wallets. A valid consensus requires exactly ten
independent, explicitly validated entities for the requested asset.

Research-only: this module does not modify Production score, threshold,
direction, geometry, or execution eligibility.
"""
from __future__ import annotations

import math
from collections import Counter

SCHEMA = "ATLAS_WHALE10_CONSENSUS_V1"
REQUIRED_ENTITIES = 10
EXCLUDED_ENTITY_TYPES = {"EXCHANGE", "CUSTODIAN", "BRIDGE", "BURN", "TREASURY_UNKNOWN"}


def _f(value, default=None):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def classify_entity(row):
    """Classify one validated entity as accumulation/distribution/neutral.

    Preferred input is normalized net-flow z-score. A percentage balance change
    can be used as a conservative fallback. No raw holder rank is treated as a
    directional signal.
    """
    z = _f(row.get("netflow_z"))
    pct = _f(row.get("balance_change_pct"))
    if z is not None:
        if z >= 0.75:
            return "ACCUMULATING"
        if z <= -0.75:
            return "DISTRIBUTING"
        return "NEUTRAL"
    if pct is not None:
        if pct >= 0.50:
            return "ACCUMULATING"
        if pct <= -0.50:
            return "DISTRIBUTING"
    return "NEUTRAL"


def validate_entities(rows, symbol):
    symbol = str(symbol or "").upper()
    accepted = []
    rejected = []
    seen = set()

    for raw in rows or []:
        row = dict(raw or {})
        entity_id = str(row.get("entity_id") or "").strip()
        row_symbol = str(row.get("symbol") or "").upper()
        entity_type = str(row.get("entity_type") or "UNKNOWN").upper()
        validated = bool(row.get("validated"))
        independent = bool(row.get("independent", True))
        reason = None

        if not entity_id:
            reason = "MISSING_ENTITY_ID"
        elif entity_id in seen:
            reason = "DUPLICATE_ENTITY"
        elif row_symbol != symbol:
            reason = "SYMBOL_MISMATCH"
        elif not validated:
            reason = "NOT_VALIDATED"
        elif not independent:
            reason = "NOT_INDEPENDENT"
        elif entity_type in EXCLUDED_ENTITY_TYPES:
            reason = f"EXCLUDED_{entity_type}"
        elif row.get("source_confidence") not in ("HIGH", "MEDIUM"):
            reason = "INSUFFICIENT_SOURCE_CONFIDENCE"

        if reason:
            rejected.append({"entity_id": entity_id or None, "reason": reason})
            continue

        seen.add(entity_id)
        accepted.append(row)

    return accepted, rejected


def build_consensus(rows, symbol):
    accepted, rejected = validate_entities(rows, symbol)
    complete = len(accepted) == REQUIRED_ENTITIES

    if not complete:
        return {
            "schema": SCHEMA,
            "symbol": str(symbol or "").upper(),
            "status": "INSUFFICIENT_VALIDATED_WHALES",
            "required": REQUIRED_ENTITIES,
            "validated_entities": len(accepted),
            "rejected_entities": rejected,
            "consensus": None,
            "consensus_score": None,
            "production_eligible": False,
            "research_only": True,
        }

    states = [classify_entity(x) for x in accepted]
    counts = Counter(states)
    signed = counts["ACCUMULATING"] - counts["DISTRIBUTING"]
    score = round(100.0 * signed / REQUIRED_ENTITIES, 1)
    if score >= 40:
        consensus = "ACCUMULATION"
    elif score <= -40:
        consensus = "DISTRIBUTION"
    else:
        consensus = "MIXED"

    entities = []
    for row, state in zip(accepted, states):
        entities.append({
            "entity_id": row.get("entity_id"),
            "entity_type": row.get("entity_type"),
            "state": state,
            "netflow_z": _f(row.get("netflow_z")),
            "balance_change_pct": _f(row.get("balance_change_pct")),
            "source_confidence": row.get("source_confidence"),
            "observed_at": row.get("observed_at"),
        })

    return {
        "schema": SCHEMA,
        "symbol": str(symbol or "").upper(),
        "status": "READY_RESEARCH_ONLY",
        "required": REQUIRED_ENTITIES,
        "validated_entities": REQUIRED_ENTITIES,
        "counts": {
            "accumulating": counts["ACCUMULATING"],
            "neutral": counts["NEUTRAL"],
            "distributing": counts["DISTRIBUTING"],
        },
        "consensus": consensus,
        "consensus_score": score,
        "entities": entities,
        "rejected_entities": rejected,
        "production_eligible": False,
        "promotion_rule": "FORWARD_VALIDATE_BEFORE_PRODUCTION_INFLUENCE",
        "research_only": True,
    }
