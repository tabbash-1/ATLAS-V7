#!/usr/bin/env python3
"""Build the research-only raw-market radar from fully closed 1h candles."""
import json
import time
import urllib.parse
import urllib.request
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
BINANCE_USDM_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"\nHYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"


def last_closed_candle_open_ms(now_ms):
    """Return the open time of the most recent fully closed 1h candle."""
    return (int(now_ms) // HOUR_MS) * HOUR_MS - HOUR_MS


def fetch_hype_futures_1h(days, end_ms):
    """Fetch paginated Binance USD-M HYPE candles; the spot listing is too new."""
    need = days * 24 + 300
    rows_by_time = {}
    cursor_ms = int(end_ms)
    while len(rows_by_time) < need:
        limit = min(1000, need - len(rows_by_time))
        query = urllib.parse.urlencode({
            "symbol": "HYPEUSDT",
            "interval": "1h",
            "limit": limit,
            "endTime": cursor_ms,
        })
        url = BINANCE_USDM_KLINES_URL + "?" + query
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
        if not payload:
            break
        batch = [
            {
                "t": int(row[0]), "o": float(row[1]), "h": float(row[2]),
                "l": float(row[3]), "c": float(row[4]), "v": float(row[5]),
            }
            for row in payload
        ]
        new_rows = {row["t"]: row for row in batch if row["t"] not in rows_by_time}
        if not new_rows:
            break
        rows_by_time.update(new_rows)
        cursor_ms = min(new_rows) - 1
        time.sleep(0.05)
    return [rows_by_time[t] for t in sorted(rows_by_time)][-need:]


def fetch_hype_hyperliquid_1h(days, end_ms):
    """Fetch HYPE perpetual 1h candles from Hyperliquid's official candleSnapshot API."""
    need = days * 24 + 300
    start_ms = int(end_ms) - (need + 24) * HOUR_MS
    body = json.dumps({
        "type": "candleSnapshot",
        "req": {"coin": "HYPE", "interval": "1h", "startTime": start_ms, "endTime": int(end_ms) + HOUR_MS - 1},
    }).encode("utf-8")
    request = urllib.request.Request(
        HYPERLIQUID_INFO_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    rows = [{
        "t": int(row["t"]), "o": float(row["o"]), "h": float(row["h"]),
        "l": float(row["l"]), "c": float(row["c"]), "v": float(row["v"]),
    } for row in payload if int(row["t"]) <= int(end_ms)]
    rows.sort(key=lambda row: row["t"])
    return rows[-need:]


def fetch_universe(now_ms):
    """Fetch every required asset; fail closed rather than publish partial data."""
    candle_end_ms = last_closed_candle_open_ms(now_ms)
    data = {}
    data_sources = {}
    failures = []
    for symbol in SYMBOLS:
        try:
            if symbol == "HYPEUSDT":
                rows = fetch_hype_futures_1h(15, candle_end_ms)
                data_sources[symbol] = "binance_usdm_perpetual"
            else:
                rows = fetch_1h(symbol, 15, candle_end_ms)
                data_sources[symbol] = "binance_spot"
            if len(rows) < MIN_1H_CANDLES:
                failures.append(f"{symbol}: insufficient candles ({len(rows)})")
            else:
                data[symbol] = rows
        except Exception as exc:
            failures.append(f"{symbol}: {type(exc).__name__}")
    if failures:
        raise RuntimeError("Raw-market radar snapshot incomplete: " + "; ".join(failures))
    return data, candle_end_ms, data_sources


def main():
    generated_at_ms = int(time.time() * 1000)
    data, candle_open_ms, data_sources = fetch_universe(generated_at_ms)
    out = build(data)
    out["generated_at_ms"] = generated_at_ms
    out["latest_closed_candle_open_ms"] = candle_open_ms
    out["requested_assets"] = len(SYMBOLS)
    out["scanned_assets"] = len(data)
    out["data_source_by_asset"] = data_sources
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["top_candidates"], sort_keys=True))


if __name__ == "__main__":
    main()
