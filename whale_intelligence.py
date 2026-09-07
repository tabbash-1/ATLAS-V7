#!/usr/bin/env python3
"""Verified whale-intelligence read model for ATLAS Production.

This module is deliberately fail-closed. It never fabricates whale identities,
transactions, exchange labels, holdings, or consensus. Production may only serve
a whale row that already carries verifiable provenance in the committed snapshot.

A separate authenticated collector is expected to write:
  status/whale-intelligence-latest.json
using a supported attribution provider (initial target: Whale Alert API).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

VERSION = "ATLAS_WHALE_INTELLIGENCE_V1_FAIL_CLOSED"
SNAPSHOT_VERSION = "ATLAS_WHALE_SNAPSHOT_V1_VERIFIED_ONLY"
STALE_AFTER_MINUTES = 20.0
MAX_AGE_HOURS = 24.0
MIN_CONFIDENCE = 0.60
ALLOWED_FLOW_TYPES = {
    "EXCHANGE_DEPOSIT",
    "EXCHANGE_WITHDRAWAL",
    "LARGE_TRANSFER",
    "MINT",
    "BURN",
}
ALLOWED_BIASES = {"ACCUMULATION", "DISTRIBUTION", "NEUTRAL"}
SUPPORTED_PROVIDER_TYPES = {"WHALE_ALERT", "VERIFIED_ONCHAIN_PROVIDER"}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_ts(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
        stamp = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=dt.timezone.utc)
        return stamp.astimezone(dt.timezone.utc)
    except Exception:
        return None


def _short_wallet(address: str) -> str:
    address = str(address or "").strip()
    if len(address) <= 14:
        return address
    return f"{address[:6]}...{address[-4:]}"


def _anonymous_label(index: int, address: str) -> str:
    return f"Whale #{index:02d} — {_short_wallet(address)}"


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _row_key(row: Dict[str, Any]) -> str:
    explicit = str(row.get("dedupe_key") or "").strip()
    if explicit:
        return explicit
    basis = "|".join([
        str(row.get("chain") or "").lower(),
        str(row.get("transaction_hash") or "").lower(),
        str(row.get("asset") or "").upper(),
        str(row.get("wallet_address") or "").lower(),
        str(row.get("flow_type") or "").upper(),
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _validate_row(raw: Any, now: dt.datetime) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "ROW_NOT_OBJECT"
    required = (
        "wallet_address", "chain", "asset", "amount", "usd_value",
        "flow_type", "bias", "transaction_timestamp", "transaction_hash",
        "source", "source_url", "confidence", "last_updated",
    )
    missing = [key for key in required if raw.get(key) in (None, "")]
    if missing:
        return None, "MISSING_" + "_".join(missing[:4]).upper()

    provider_type = str(raw.get("provider_type") or "").upper()
    if provider_type not in SUPPORTED_PROVIDER_TYPES:
        return None, "UNVERIFIED_PROVIDER"
    flow_type = str(raw.get("flow_type") or "").upper()
    if flow_type not in ALLOWED_FLOW_TYPES:
        return None, "INVALID_FLOW_TYPE"
    bias = str(raw.get("bias") or "").upper()
    if bias not in ALLOWED_BIASES:
        return None, "INVALID_BIAS"
    confidence = _safe_float(raw.get("confidence"))
    amount = _safe_float(raw.get("amount"))
    usd_value = _safe_float(raw.get("usd_value"))
    if confidence is None or confidence < MIN_CONFIDENCE or confidence > 1.0:
        return None, "LOW_OR_INVALID_CONFIDENCE"
    if amount is None or amount <= 0 or usd_value is None or usd_value <= 0:
        return None, "INVALID_AMOUNT"

    tx_ts = _parse_ts(raw.get("transaction_timestamp"))
    updated = _parse_ts(raw.get("last_updated"))
    if tx_ts is None or updated is None:
        return None, "INVALID_TIMESTAMP"
    age_hours = max(0.0, (now - tx_ts).total_seconds() / 3600.0)
    if age_hours > MAX_AGE_HOURS:
        return None, "TRANSACTION_TOO_OLD"

    internal = bool(raw.get("internal_transfer") or raw.get("self_transfer"))
    if internal:
        return None, "INTERNAL_TRANSFER"

    address = str(raw.get("wallet_address") or "").strip()
    entity_name = str(raw.get("entity_name") or "").strip()
    attribution_verified = bool(raw.get("attribution_verified"))
    if entity_name and not attribution_verified:
        entity_name = ""

    exchange_name = str(raw.get("exchange_name") or "").strip()
    exchange_verified = bool(raw.get("exchange_attribution_verified"))
    if exchange_name and not exchange_verified:
        exchange_name = ""

    row = {
        "wallet_address": address,
        "entity_name": entity_name or None,
        "attribution_verified": attribution_verified,
        "chain": str(raw.get("chain") or "").lower(),
        "estimated_holdings": raw.get("estimated_holdings") if raw.get("holdings_verified") else None,
        "holdings_verified": bool(raw.get("holdings_verified")),
        "asset": str(raw.get("asset") or "").upper(),
        "amount": amount,
        "usd_value": usd_value,
        "flow_type": flow_type,
        "exchange_name": exchange_name or None,
        "exchange_attribution_verified": exchange_verified,
        "bias": bias,
        "transaction_timestamp": tx_ts.isoformat().replace("+00:00", "Z"),
        "transaction_hash": str(raw.get("transaction_hash")),
        "source": str(raw.get("source")),
        "source_url": str(raw.get("source_url")),
        "provider_type": provider_type,
        "confidence": confidence,
        "last_updated": updated.isoformat().replace("+00:00", "Z"),
        "freshness_minutes": round(max(0.0, (now - updated).total_seconds() / 60.0), 2),
        "freshness": "LIVE" if (now - updated).total_seconds() <= 300 else "DELAYED",
        "internal_transfer": False,
    }
    row["dedupe_key"] = _row_key(row)
    return row, None


def _dedupe(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("dedupe_key"))
        previous = by_key.get(key)
        if previous is None or float(row.get("confidence") or 0) > float(previous.get("confidence") or 0):
            by_key[key] = row
    return list(by_key.values())


def _weight(row: Dict[str, Any], now: dt.datetime) -> float:
    tx_ts = _parse_ts(row.get("transaction_timestamp")) or now
    age_hours = max(0.0, (now - tx_ts).total_seconds() / 3600.0)
    recency = math.exp(-age_hours / 8.0)
    size = math.log10(max(100000.0, float(row.get("usd_value") or 0.0))) - 4.0
    size = max(0.25, min(4.0, size))
    type_factor = {
        "EXCHANGE_WITHDRAWAL": 1.00,
        "EXCHANGE_DEPOSIT": 1.00,
        "MINT": 0.65,
        "BURN": 0.65,
        "LARGE_TRANSFER": 0.35,
    }.get(str(row.get("flow_type")), 0.25)
    return size * recency * type_factor * float(row.get("confidence") or 0.0)


def _consensus(rows: List[Dict[str, Any]], now: dt.datetime) -> Dict[str, Any]:
    if not rows:
        return {
            "status": "INSUFFICIENT_DATA", "whale_bias": "INSUFFICIENT DATA",
            "confidence": 0.0, "accumulating": 0, "distributing": 0, "neutral": 0,
            "net_verified_flow_usd": None, "sample_size": 0,
            "method": "size x recency x provenance-confidence x flow-type; deduplicated; internal transfers excluded",
        }
    signed = 0.0
    total_weight = 0.0
    net_flow = 0.0
    counts = {"ACCUMULATION": 0, "DISTRIBUTION": 0, "NEUTRAL": 0}
    for row in rows:
        bias = str(row.get("bias"))
        counts[bias] = counts.get(bias, 0) + 1
        weight = _weight(row, now)
        total_weight += weight
        direction = 1.0 if bias == "ACCUMULATION" else -1.0 if bias == "DISTRIBUTION" else 0.0
        signed += direction * weight
        if row.get("flow_type") == "EXCHANGE_WITHDRAWAL":
            net_flow += float(row.get("usd_value") or 0.0)
        elif row.get("flow_type") == "EXCHANGE_DEPOSIT":
            net_flow -= float(row.get("usd_value") or 0.0)
    strength = signed / total_weight if total_weight > 0 else 0.0
    if len(rows) < 3 or total_weight < 0.75:
        status = "INSUFFICIENT_DATA"
        bias_label = "INSUFFICIENT DATA"
    elif strength >= 0.20:
        status = "BULLISH"
        bias_label = "BULLISH"
    elif strength <= -0.20:
        status = "BEARISH"
        bias_label = "BEARISH"
    else:
        status = "MIXED"
        bias_label = "MIXED"
    confidence = min(0.95, abs(strength) * min(1.0, len(rows) / 10.0)) if status != "INSUFFICIENT_DATA" else 0.0
    return {
        "status": status,
        "whale_bias": bias_label,
        "confidence": round(confidence, 4),
        "accumulating": counts.get("ACCUMULATION", 0),
        "distributing": counts.get("DISTRIBUTION", 0),
        "neutral": counts.get("NEUTRAL", 0),
        "net_verified_flow_usd": round(net_flow, 2),
        "sample_size": len(rows),
        "method": "size x recency x provenance-confidence x flow-type; deduplicated; internal transfers excluded",
    }


def load_snapshot(base: Path, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    now = now or _utcnow()
    path = Path(base) / "status" / "whale-intelligence-latest.json"
    base_payload: Dict[str, Any] = {
        "ok": True,
        "version": VERSION,
        "snapshot_version": SNAPSHOT_VERSION,
        "state": "DATA_UNAVAILABLE",
        "data_available": False,
        "provider": None,
        "provider_authenticated": False,
        "top10": [],
        "feed": [],
        "consensus": _consensus([], now),
        "rejected_rows": 0,
        "rejection_reasons": {},
        "last_updated": None,
        "stale_after_minutes": STALE_AFTER_MINUTES,
        "research_only": True,
        "analysis_only": True,
        "live_execution": False,
        "can_override_production": False,
        "message": "DATA UNAVAILABLE — no verified whale snapshot is available in Production.",
    }
    if not path.exists():
        return base_payload
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != SNAPSHOT_VERSION:
            base_payload["message"] = "DATA UNAVAILABLE — whale snapshot version is not trusted."
            return base_payload
        provider = payload.get("provider") or {}
        provider_type = str(provider.get("type") or "").upper()
        if provider_type not in SUPPORTED_PROVIDER_TYPES or not bool(provider.get("authenticated")):
            base_payload["message"] = "DATA UNAVAILABLE — verified authenticated whale provider is not configured."
            return base_payload
        captured = _parse_ts(payload.get("captured_at"))
        if captured is None:
            base_payload["message"] = "DATA UNAVAILABLE — whale snapshot timestamp is invalid."
            return base_payload
        age_minutes = max(0.0, (now - captured).total_seconds() / 60.0)
        if age_minutes > STALE_AFTER_MINUTES:
            base_payload.update({
                "provider": provider.get("name"), "provider_authenticated": True,
                "last_updated": captured.isoformat().replace("+00:00", "Z"),
                "snapshot_age_minutes": round(age_minutes, 2),
                "message": "DATA UNAVAILABLE — latest verified whale snapshot is stale.",
            })
            return base_payload

        valid_rows: List[Dict[str, Any]] = []
        rejection_reasons: Dict[str, int] = {}
        for raw in payload.get("transactions") or []:
            row, reason = _validate_row(raw, now)
            if row is not None:
                valid_rows.append(row)
            else:
                rejection_reasons[reason or "UNKNOWN"] = rejection_reasons.get(reason or "UNKNOWN", 0) + 1
        valid_rows = _dedupe(valid_rows)
        valid_rows.sort(key=lambda r: (str(r.get("transaction_timestamp")), float(r.get("usd_value") or 0.0)), reverse=True)

        # Top whales are unique wallets ranked by verified recent flow magnitude,
        # then relabelled anonymously unless attribution was explicitly verified.
        wallets: Dict[str, Dict[str, Any]] = {}
        for row in valid_rows:
            address = str(row.get("wallet_address") or "").lower()
            slot = wallets.setdefault(address, {"score": 0.0, "latest": row})
            slot["score"] += _weight(row, now) * float(row.get("usd_value") or 0.0)
            if str(row.get("transaction_timestamp")) > str(slot["latest"].get("transaction_timestamp")):
                slot["latest"] = row
        ranked = sorted(wallets.values(), key=lambda x: x["score"], reverse=True)[:10]
        top10 = []
        for idx, slot in enumerate(ranked, 1):
            row = dict(slot["latest"])
            row["display_name"] = row.get("entity_name") if row.get("attribution_verified") and row.get("entity_name") else _anonymous_label(idx, row.get("wallet_address") or "")
            row["verified_activity_score"] = round(float(slot["score"]), 2)
            top10.append(row)

        if not valid_rows:
            base_payload.update({
                "provider": provider.get("name"), "provider_authenticated": True,
                "rejected_rows": sum(rejection_reasons.values()), "rejection_reasons": rejection_reasons,
                "last_updated": captured.isoformat().replace("+00:00", "Z"),
                "message": "DATA UNAVAILABLE — provider snapshot contained no rows that passed provenance validation.",
            })
            return base_payload

        return {
            **base_payload,
            "state": "VERIFIED_DATA_AVAILABLE",
            "data_available": True,
            "provider": provider.get("name"),
            "provider_authenticated": True,
            "top10": top10,
            "feed": valid_rows[:100],
            "consensus": _consensus(valid_rows, now),
            "rejected_rows": sum(rejection_reasons.values()),
            "rejection_reasons": rejection_reasons,
            "last_updated": captured.isoformat().replace("+00:00", "Z"),
            "snapshot_age_minutes": round(age_minutes, 2),
            "message": "Verified whale data available.",
        }
    except Exception as exc:
        base_payload["message"] = f"DATA UNAVAILABLE — whale snapshot could not be validated: {type(exc).__name__}."
        return base_payload


def filter_feed(snapshot: Dict[str, Any], asset: Optional[str] = None, flow_type: Optional[str] = None, bias: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list(snapshot.get("feed") or [])
    if asset:
        rows = [r for r in rows if str(r.get("asset") or "").upper() == str(asset).upper()]
    if flow_type:
        rows = [r for r in rows if str(r.get("flow_type") or "").upper() == str(flow_type).upper()]
    if bias:
        rows = [r for r in rows if str(r.get("bias") or "").upper() == str(bias).upper()]
    return rows
