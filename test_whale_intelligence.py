#!/usr/bin/env python3
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from whale_intelligence import load_snapshot


NOW = dt.datetime(2026, 9, 7, 20, 0, tzinfo=dt.timezone.utc)


def row(**overrides):
    base = {
        "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        "entity_name": "Unverified Fancy Fund",
        "attribution_verified": False,
        "chain": "ethereum",
        "asset": "ETH",
        "amount": 2500,
        "usd_value": 10000000,
        "flow_type": "EXCHANGE_WITHDRAWAL",
        "exchange_name": "Some Exchange",
        "exchange_attribution_verified": False,
        "bias": "ACCUMULATION",
        "transaction_timestamp": "2026-09-07T19:55:00Z",
        "transaction_hash": "0xabc123",
        "source": "Whale Alert",
        "source_url": "https://example.invalid/source/0xabc123",
        "provider_type": "WHALE_ALERT",
        "confidence": 0.90,
        "last_updated": "2026-09-07T19:58:00Z",
    }
    base.update(overrides)
    return base


def write_snapshot(base: Path, transactions, captured_at="2026-09-07T19:59:00Z", provider=None):
    status = base / "status"
    status.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "ATLAS_WHALE_SNAPSHOT_V1_VERIFIED_ONLY",
        "captured_at": captured_at,
        "provider": provider or {"name": "Whale Alert", "type": "WHALE_ALERT", "authenticated": True},
        "transactions": transactions,
    }
    (status / "whale-intelligence-latest.json").write_text(json.dumps(payload), encoding="utf-8")


class WhaleIntegrityTests(unittest.TestCase):
    def test_missing_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = load_snapshot(Path(tmp), now=NOW)
        self.assertEqual(out["state"], "DATA_UNAVAILABLE")
        self.assertFalse(out["data_available"])
        self.assertEqual(out["top10"], [])
        self.assertEqual(out["feed"], [])
        self.assertEqual(out["consensus"]["status"], "INSUFFICIENT_DATA")

    def test_unverified_entity_and_exchange_names_are_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_snapshot(base, [row()])
            out = load_snapshot(base, now=NOW)
        self.assertTrue(out["data_available"])
        self.assertIsNone(out["feed"][0]["entity_name"])
        self.assertIsNone(out["feed"][0]["exchange_name"])
        self.assertTrue(out["top10"][0]["display_name"].startswith("Whale #01 — "))

    def test_internal_transfers_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_snapshot(base, [row(internal_transfer=True)])
            out = load_snapshot(base, now=NOW)
        self.assertFalse(out["data_available"])
        self.assertEqual(out["rejection_reasons"].get("INTERNAL_TRANSFER"), 1)

    def test_duplicate_transaction_is_counted_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a = row()
            b = row(confidence=0.95)
            write_snapshot(base, [a, b])
            out = load_snapshot(base, now=NOW)
        self.assertEqual(len(out["feed"]), 1)
        self.assertEqual(out["consensus"]["sample_size"], 1)
        self.assertAlmostEqual(out["feed"][0]["confidence"], 0.95)

    def test_stale_snapshot_is_not_served(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_snapshot(base, [row()], captured_at="2026-09-07T19:00:00Z")
            out = load_snapshot(base, now=NOW)
        self.assertFalse(out["data_available"])
        self.assertEqual(out["state"], "DATA_UNAVAILABLE")
        self.assertEqual(out["top10"], [])

    def test_consensus_uses_verified_directional_flow(self):
        rows = [
            row(wallet_address="0x1111111111111111111111111111111111111111", transaction_hash="0x1", usd_value=15000000, flow_type="EXCHANGE_WITHDRAWAL", bias="ACCUMULATION"),
            row(wallet_address="0x2222222222222222222222222222222222222222", transaction_hash="0x2", usd_value=12000000, flow_type="EXCHANGE_WITHDRAWAL", bias="ACCUMULATION"),
            row(wallet_address="0x3333333333333333333333333333333333333333", transaction_hash="0x3", usd_value=2000000, flow_type="EXCHANGE_DEPOSIT", bias="DISTRIBUTION"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_snapshot(base, rows)
            out = load_snapshot(base, now=NOW)
        self.assertEqual(out["consensus"]["status"], "BULLISH")
        self.assertEqual(out["consensus"]["accumulating"], 2)
        self.assertEqual(out["consensus"]["distributing"], 1)
        self.assertGreater(out["consensus"]["net_verified_flow_usd"], 0)


if __name__ == "__main__":
    unittest.main()
