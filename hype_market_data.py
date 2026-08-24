"""HYPE/USDT spot candle adapter for ATLAS Production.

This module is intentionally narrow: it only intercepts HYPEUSDT candle reads.
All other symbols continue through ATLAS' existing Binance spot path unchanged.

Provider order:
1) OKX HYPE-USDT spot 1h candles
2) Bybit HYPEUSDT spot 1h candles

No scoring, thresholds, forward logic, or trade rules are modified here.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

VERSION = "HYPE_SPOT_ADAPTER_V1"


def _f(value):
    return float(value)


def _get_json(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _okx(limit, ua):
    query = urllib.parse.urlencode({"instId": "HYPE-USDT", "bar": "1H", "limit": int(limit)})
    obj = _get_json("https://www.okx.com/api/v5/market/candles?" + query, ua)
    if str(obj.get("code")) != "0":
        raise RuntimeError(f"OKX code={obj.get('code')} msg={obj.get('msg')}")
    rows = obj.get("data") or []
    out = []
    for row in reversed(rows):  # OKX returns newest first; ATLAS expects chronological order.
        if not isinstance(row, list) or len(row) < 6:
            continue
        out.append({
            "open_time": int(row[0]),
            "open": _f(row[1]),
            "high": _f(row[2]),
            "low": _f(row[3]),
            "close": _f(row[4]),
            "volume": _f(row[5]),
        })
    if len(out) < min(100, int(limit)):
        raise RuntimeError(f"OKX insufficient HYPE candles: {len(out)}")
    return out[-int(limit):], "www.okx.com"


def _bybit(limit, ua):
    query = urllib.parse.urlencode({
        "category": "spot",
        "symbol": "HYPEUSDT",
        "interval": "60",
        "limit": int(limit),
    })
    obj = _get_json("https://api.bybit.com/v5/market/kline?" + query, ua)
    if int(obj.get("retCode", -1)) != 0:
        raise RuntimeError(f"Bybit retCode={obj.get('retCode')} msg={obj.get('retMsg')}")
    rows = ((obj.get("result") or {}).get("list") or [])
    out = []
    for row in reversed(rows):  # Bybit returns newest first.
        if not isinstance(row, list) or len(row) < 6:
            continue
        out.append({
            "open_time": int(row[0]),
            "open": _f(row[1]),
            "high": _f(row[2]),
            "low": _f(row[3]),
            "close": _f(row[4]),
            "volume": _f(row[5]),
        })
    if len(out) < min(100, int(limit)):
        raise RuntimeError(f"Bybit insufficient HYPE candles: {len(out)}")
    return out[-int(limit):], "api.bybit.com"


def install(atlas):
    original_spot_klines = atlas._spot_klines

    def spot_klines(symbol, limit=220):
        normalized = str(symbol or "").upper().replace("BINANCE:", "")
        if normalized != "HYPEUSDT":
            return original_spot_klines(symbol, limit)

        errors = []
        for fetcher in (_okx, _bybit):
            try:
                rows, provider = fetcher(limit, atlas.UA)
                if "spot" in atlas.MARKET_DATA_STATE:
                    atlas.MARKET_DATA_STATE["spot"]["last_provider"] = provider
                    atlas.MARKET_DATA_STATE["spot"]["last_success_at"] = atlas.now_iso()
                    atlas.MARKET_DATA_STATE["spot"]["last_error"] = None
                return rows
            except Exception as exc:
                errors.append(f"{fetcher.__name__}: {type(exc).__name__}: {exc}")

        message = "HYPEUSDT spot providers failed: " + " | ".join(errors)
        if "spot" in atlas.MARKET_DATA_STATE:
            atlas.MARKET_DATA_STATE["spot"]["last_error"] = message
        raise RuntimeError(message)

    atlas._spot_klines = spot_klines
    atlas.HYPE_MARKET_DATA_VERSION = VERSION
    return {"enabled": True, "version": VERSION, "symbol": "HYPEUSDT", "providers": ["OKX", "Bybit"]}
