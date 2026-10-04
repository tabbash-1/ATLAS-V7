import ast
from pathlib import Path

import pytest

import profitability_raw_market_radar as radar
import profitability_raw_market_radar_snapshot as snapshot


def candles(up=True, n=300):
    out = []
    for i in range(n):
        close = 100 + i * 0.2 if up else 200 - i * 0.2
        out.append({
            "t": i * 3600000, "o": close - 0.05, "h": close + 0.2,
            "l": close - 0.2, "c": close, "v": 200 if i == n - 1 else 100,
        })
    return out


def test_raw_radar_does_not_need_production_decisions():
    result = radar.build({"BTCUSDT": candles(True), "SOLUSDT": candles(True)})
    assert result["btc_context"]["side"] == "LONG"
    assert result["ranked_universe"][0]["radar_score"] > 0
    assert result["safety"]["can_create_trade"] is False
    assert result["safety"]["can_override_production"] is False


def test_btc_breakdown_blocks_alt_long():
    result = radar.build({"BTCUSDT": candles(False), "SOLUSDT": candles(True)})
    sol = next(row for row in result["ranked_universe"] if row["symbol"] == "SOLUSDT")
    assert sol["state"] == "BLOCKED_BTC_BREAKDOWN"


def test_scanner_requests_only_the_last_closed_hour(monkeypatch):
    symbols = ["BTCUSDT", "ETHUSDT"]
    calls = []
    monkeypatch.setattr(snapshot, "SYMBOLS", symbols)
    monkeypatch.setattr(snapshot, "fetch_1h", lambda symbol, days, end_ms:
                        calls.append((symbol, days, end_ms)) or candles())
    now_ms = 10 * snapshot.HOUR_MS + 7 * 60 * 1000

    data, candle_open_ms = snapshot.fetch_universe(now_ms)

    assert set(data) == set(symbols)
    assert candle_open_ms == 9 * snapshot.HOUR_MS
    assert calls == [(symbol, 14, 9 * snapshot.HOUR_MS) for symbol in symbols]


def test_incomplete_fetch_fails_without_replacing_snapshot(monkeypatch, tmp_path):
    target = tmp_path / "snapshot.json"
    target.write_text("previous-good-snapshot")
    monkeypatch.setattr(snapshot, "SNAPSHOT_PATH", target)
    monkeypatch.setattr(snapshot, "SYMBOLS", ["BTCUSDT", "ETHUSDT"])
    monkeypatch.setattr(snapshot.time, "time", lambda: 10 * 3600)
    def fetch(symbol, days, end_ms):
        if symbol == "ETHUSDT":
            raise OSError("temporary data source failure")
        return candles()
    monkeypatch.setattr(snapshot, "fetch_1h", fetch)

    with pytest.raises(RuntimeError, match="snapshot incomplete"):
        snapshot.main()

    assert target.read_text() == "previous-good-snapshot"


def test_radar_modules_have_no_trade_or_production_write_dependencies():
    root = Path(__file__).resolve().parents[1]
    for filename in (
        "profitability_raw_market_radar.py",
        "profitability_raw_market_radar_snapshot.py",
    ):
        tree = ast.parse((root / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.lower() for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").lower()]
            else:
                continue
            assert not any(
                forbidden in name
                for name in names
                for forbidden in ("trade_outcome", "final_trade_gate", "order_execution", "supabase")
            )
