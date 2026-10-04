#!/usr/bin/env python3
"""Build the research-only raw-market radar from fully closed 1h candles."""
import json
import time
from pathlib import Path

from historical_core_4_12h_replay import fetch_1h
from profitability_raw_market_radar import build

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT",
    "ZECUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "HYPEUSDT",
]
HOUR_MS = 60 * 60 * 1000
MIN_1H_CANDLES = 55 * 12
SNAPSHOT_PATH = Path("status/profitability-raw-market-radar-latest.json")


def last_closed_candle_open_ms(now_ms):
    """Return the open time of the most recent fully closed 1h candle."""
    return (int(now_ms) // HOUR_MS) * HOUR_MS - HOUR_MS


def fetch_universe(now_ms):
    """Fetch every required asset; fail closed rather than publish partial data."""
    candle_end_ms = last_closed_candle_open_ms(now_ms)
    data = {}
    failures = []
    for symbol in SYMBOLS:
        try:
            rows = fetch_1h(symbol, 15, candle_end_ms)
            if len(rows) < MIN_1H_CANDLES:
                failures.append(f"{symbol}: insufficient candles ({len(rows)})")
            else:
                data[symbol] = rows
        except Exception as exc:
            failures.append(f"{symbol}: {type(exc).__name__}")
    if failures:
        raise RuntimeError("Raw-market radar snapshot incomplete: " + "; ".join(failures))
    return data, candle_end_ms


def main():
    generated_at_ms = int(time.time() * 1000)
    data, candle_open_ms = fetch_universe(generated_at_ms)
    out = build(data)
    out["generated_at_ms"] = generated_at_ms
    out["latest_closed_candle_open_ms"] = candle_open_ms
    out["requested_assets"] = len(SYMBOLS)
    out["scanned_assets"] = len(data)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["top_candidates"], sort_keys=True))


if __name__ == "__main__":
    main()
