"""Deterministic mock-Bybit regressions for frozen Edge venue forward evidence."""
from __future__ import annotations

import io
import json
import tempfile
import urllib.parse
from pathlib import Path

from research.edge_bybit_venue_forward_v1 import (
    HOUR_MS, MINUTE_MS, HORIZON_MIN, POLICIES, SYMBOLS,
    _settle, book_snapshot, digest, freeze, load, market_candles, run,
)

NOW = 150 * HOUR_MS + 13 * MINUTE_MS


class Market:
    def __init__(self, now=NOW, stale_quote=False, missing_minute=False):
        self.now = now
        self.stale_quote = stale_quote
        self.missing_minute = missing_minute
        self.calls = []

    def __call__(self, url, timeout=20):
        u = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(u.query)
        self.calls.append((u.path, q))
        sym = q["symbol"][0]
        if u.path == "/v5/market/tickers":
            body = {
                "retCode": 0, "time": self.now - (120000 if self.stale_quote else 0),
                "result": {"list": [{"symbol": sym, "bid1Price": "100",
                         "ask1Price": "100.1", "bid1Size": "1.2",
                         "ask1Size": "2.5"}]},
            }
        else:
            step = int(q["interval"][0]) * MINUTE_MS
            if step == HOUR_MS:
                end = self.now // HOUR_MS * HOUR_MS - HOUR_MS
                times = [end - i * HOUR_MS for i in range(100)]
                def values(t):
                    i = (t // HOUR_MS)
                    p = 100 + .04 * i
                    return p, p + 1, p - 1, p
            else:
                start = int(q["start"][0])
                end = int(q["end"][0])
                times = [start + i * MINUTE_MS for i in range(HORIZON_MIN)]
                if self.missing_minute:
                    times.pop(100)
                def values(t):
                    return 101, 101.2, 100.8, 101.0
            rows = []
            for t in reversed(times):
                a, hi, lo, close = values(t)
                rows.append([str(t),str(a),str(hi),str(lo),str(close),"300","300"])
            body = {"retCode": 0, "time": self.now,
                    "result": {"category": "linear", "symbol": sym, "list": rows}}
        return io.BytesIO(json.dumps(body).encode())


def test_live_quote_and_causal_closed_candles():
    m = Market()
    hist = market_candles("BTCUSDT", 60, NOW, request_fn=m)
    assert len(hist) == 100
    assert hist[-1]["time"] == 149 * HOUR_MS
    book = book_snapshot("BTCUSDT", NOW, request_fn=m)
    assert book["bid"] == 100 and book["ask"] == 100.1
    assert book["quote_at_ms"] == NOW
    entries = freeze("BTCUSDT", hist, hist, book, NOW)
    assert {x["policy"] for x in entries} == set(POLICIES)
    assert all(x["capture_sha256"] == digest(x) for x in entries)
    assert all(x["research_only"] and not x["can_create_trade"] for x in entries)
    assert all(x["settlement_window_start_ms"] > NOW for x in entries)
    assert all(x["features"]["observed_close_time_ms"] < x["quote_at_ms"]
               for x in entries)


def test_run_persists_immutable_snapshots_and_settles_later():
    with tempfile.TemporaryDirectory() as d:
        lp = str(Path(d) / "ledger.json")
        latest = str(Path(d) / "latest.json")
        m = Market()
        first = run(NOW, m, lp, latest)
        assert first["observations"] == len(SYMBOLS) * len(POLICIES)
        assert len(first["new_observation_ids"]) == first["observations"]
        assert first["settled_directional_count"] == 0
        original = load(lp)
        old_snapshots = {x["id"]: x["capture_sha256"] for x in original["observations"]}
        second = run(NOW, m, lp, latest)
        assert second["new_observation_ids"] == []
        assert {x["id"]: x["capture_sha256"] for x in load(lp)["observations"]} == old_snapshots

        before_maturity = run(NOW + 8 * HOUR_MS, Market(NOW + 8 * HOUR_MS), lp, latest)
        assert before_maturity["settled_directional_count"] == 0
        after = run(NOW + 13 * HOUR_MS, Market(NOW + 13 * HOUR_MS), lp, latest)
        assert after["settled_directional_count"] > 0
        assert after["profitability_validated"] is False
        assert after["can_override_final_trade_gate"] is False
        frozen_now = load(lp)
        assert all(x["capture_sha256"] == digest(x) for x in frozen_now["observations"])
        assert all(oid in frozen_now["outcomes"] for oid in old_snapshots
                   if next(x for x in original["observations"] if x["id"] == oid)["direction"] != "WAIT")


def test_missing_future_minute_refuses_to_settle_and_retry():
    with tempfile.TemporaryDirectory() as d:
        lp = str(Path(d) / "ledger.json")
        lt = str(Path(d) / "latest.json")
        run(NOW, Market(), lp, lt)
        x = run(NOW + 13 * HOUR_MS,
                Market(NOW + 13 * HOUR_MS, missing_minute=True), lp, lt)
        assert x["settled_directional_count"] == 0
        assert x["pending_directional"] > 0
        assert any(k.startswith("SETTLE_") for k in x["errors"])
        y = run(NOW + 14 * HOUR_MS, Market(NOW + 14 * HOUR_MS), lp, lt)
        assert y["settled_directional_count"] > 0


def test_stale_quote_cannot_create_fictional_signal():
    with tempfile.TemporaryDirectory() as d:
        x = run(NOW, Market(stale_quote=True),
                str(Path(d) / "ledger.json"),
                str(Path(d) / "latest.json"))
        assert x["observations"] == 0
        assert set(SYMBOLS).issubset(x["errors"])


def test_no_catch_up_after_missed_close():
    m = Market()
    bars = market_candles("BTCUSDT", 60, NOW, request_fn=m)
    book = book_snapshot("BTCUSDT", NOW, request_fn=m)
    try:
        freeze("BTCUSDT", bars, bars, book, NOW + 35 * MINUTE_MS)
    except ValueError as ex:
        assert "Missed capture" in str(ex)
    else:
        raise AssertionError("Must not backfill missed interval")


def test_first_hit_ambiguous_minute_and_execution_cost_only_scenario():
    m = Market()
    hist = market_candles("BTCUSDT", 60, NOW, request_fn=m)
    book = book_snapshot("BTCUSDT", NOW, request_fn=m)
    rows = freeze("BTCUSDT", hist, hist, book, NOW)
    long = next(x for x in rows if x["direction"] == "LONG")
    start = long["settlement_window_start_ms"]
    bars = [{"time": start + i * MINUTE_MS, "close": long["entry_side_quote"],
             "open": long["entry_side_quote"], "high": long["entry_side_quote"] + .1,
             "low": long["entry_side_quote"] - .1} for i in range(HORIZON_MIN)]
    bars[0]["high"] = long["take_profit"] + 1
    bars[0]["low"] = long["stop_loss"] - 1
    out = _settle(long, bars)
    assert out["outcome"] == "AMBIGUOUS_1M_ORDER"
    assert out["modeled_net_r"] is None
    bars[0]["high"] = long["entry_side_quote"] + .1
    bars[0]["low"] = long["stop_loss"] - 1
    out = _settle(long, bars)
    assert out["outcome"] == "SL_FIRST"
    assert out["modeled_net_r"] < out["gross_r"]
    assert out["actual_fills_or_funding_measured"] is False


def test_frozen_hash_tamper_detection():
    with tempfile.TemporaryDirectory() as d:
        lp = str(Path(d) / "ledger.json")
        run(NOW, Market(), lp, str(Path(d) / "latest.json"))
        rows = json.loads(Path(lp).read_text())
        rows["observations"][0]["direction"] = "SHORT"
        Path(lp).write_text(json.dumps(rows))
        try:
            load(lp)
        except ValueError as ex:
            assert "mutated" in str(ex)
        else:
            raise AssertionError("Altered frozen observation must be rejected")


if __name__ == "__main__":
    test_live_quote_and_causal_closed_candles()
    test_run_persists_immutable_snapshots_and_settles_later()
    test_missing_future_minute_refuses_to_settle_and_retry()
    test_stale_quote_cannot_create_fictional_signal()
    test_no_catch_up_after_missed_close()
    test_first_hit_ambiguous_minute_and_execution_cost_only_scenario()
    test_frozen_hash_tamper_detection()
    print("Bybit venue forward shadow regression: ok")
