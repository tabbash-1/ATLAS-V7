#!/usr/bin/env python3
"""ATLAS V1.0 product release contract.

This module separates two different questions that must never be conflated:
1) Is the product technically ready to be used as a 4-12H analysis system?
2) Has independent forward evidence validated a profitable edge?

ATLAS may be READY_FOR_ANALYSIS while forward validation is still pending.
That is not permission to claim profitability and it never enables execution.
"""
from __future__ import annotations

import json
from pathlib import Path

RELEASE_VERSION = "ATLAS_V1_0_RC1"
CONTRACT_VERSION = "ATLAS_RELEASE_CONTRACT_V1"
CANONICAL_CONTRACT = "analyst_output"
PRODUCT_HORIZON = "4-12H"


def _load_readiness(base: Path):
    path = Path(base) / "status" / "product-readiness-latest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("readiness snapshot is not an object")
        return payload, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def build_product_status(base: Path):
    readiness, error = _load_readiness(Path(base))
    technical_ready = bool(
        readiness
        and readiness.get("technical_ready") is True
        and readiness.get("canonical_contract") == CANONICAL_CONTRACT
        and readiness.get("product_horizon") == PRODUCT_HORIZON
        and readiness.get("analysis_only") is True
        and readiness.get("live_execution") is False
        and readiness.get("production_score_threshold_changed") is False
    )
    forward_ready = bool(readiness and readiness.get("forward_evidence_ready") is True)

    return {
        "ok": technical_ready,
        "release_contract": CONTRACT_VERSION,
        "release_version": RELEASE_VERSION,
        "product_status": "READY_FOR_ANALYSIS" if technical_ready else "NOT_READY",
        "canonical_contract": CANONICAL_CONTRACT,
        "product_horizon": PRODUCT_HORIZON,
        "analysis_only": True,
        "live_execution": False,
        "order_routing": False,
        "technical_ready": technical_ready,
        "forward_validation": "VALIDATED" if forward_ready else "EVIDENCE_PENDING",
        "forward_evidence_ready": forward_ready,
        "profitability_validated": bool(
            forward_ready
            and readiness
            and (readiness.get("claim_policy") or {}).get("may_claim_profitable") is True
        ),
        "may_claim_technically_operational": bool(
            readiness
            and (readiness.get("claim_policy") or {}).get("may_claim_technically_operational") is True
        ),
        "readiness_state": readiness.get("state") if readiness else None,
        "readiness_generated_at": readiness.get("generated_at") if readiness else None,
        "forward_observed": (readiness or {}).get("observed") or {},
        "evidence_requirements": (readiness or {}).get("preregistered_evidence_requirements") or {},
        "readiness_snapshot_error": error,
        "score_or_threshold_changed_by_release": False,
        "can_override_production": False,
        "note": "Operational readiness is separate from forward profitability validation."
    }
