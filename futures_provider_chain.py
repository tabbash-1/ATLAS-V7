"""ATLAS public futures provider chain.

Purpose:
- keep the existing Binance/Kraken/Hyperliquid path as first choice;
- recover non-HYPE symbols when the primary futures path is blocked (e.g. HTTP 403);
- normalize OKX/Bybit public derivatives data into ATLAS_SM_V2 fields;
- expose provider health explicitly.

This module does not change score thresholds, signal rules, geometry, or execution.
Fallback snapshots are considered Production-validated only when the normalized
contract has mark price, funding, open interest, order-book imbalance and a
trade-flow ratio from public taker-side trades.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

VERSION = "FUTURES_PROVIDER_CHAIN_V1"
PROVIDERS = ("OKX_USDT_SWAP_PUBLIC", "BYBIT_LINEAR_PUBLIC")


def _f(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_json(url, ua, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _flow_ratio(trades):
    buy = sell = 0.0
    for row in trades or []:
        side = str(row.get("side") or "").lower()
        size = _f(row.get("sz") if "sz" in row else row.get("size"), 0.0) or 0.0
        if side == "buy":
            buy += size
        elif side == "sell":
            sell += size
    if buy <= 0 and sell <= 0:
        return None, buy, sell
    return (buy / sell if sell > 0 else 3.0), buy, sell


def _book_metrics(atlas, bids, asks, mark):
    depth = {"bids": bids or [], "asks": asks or []}
    bidn, askn, imbalance = atlas.orderbook_metrics(depth)
    walls = atlas.liquidity_walls(depth, mark)
    return bidn, askn, imbalance, walls


def _previous_oi_change(atlas, symbol, provider, oi):
    prev = atlas.previous_provider(symbol, provider)
    prev_oi = _f(prev.get("open_interest")) if prev else None
    if oi is None or not prev_oi:
        return None
    return ((oi / prev_oi) - 1.0) * 100.0


def _validated(mark, funding, oi, imbalance, taker_ratio):
    return all(v is not None for v in (mark, funding, oi, imbalance, taker_ratio))


def _snapshot(atlas, symbol, provider, mark, index, funding, next_funding, oi,
              taker_ratio, buy_vol, sell_vol, bidn, askn, imbalance, walls,
              price_change_24h, quote_volume_24h, sources):
    oi_change = _previous_oi_change(atlas, symbol, provider, oi)
    score = atlas.score_snapshot(funding, taker_ratio, imbalance, oi_change)
    validated = _validated(mark, funding, oi, imbalance, taker_ratio)
    return {
        "schema": "ATLAS_SM_V2",
        "captured_at": atlas.now_iso(),
        "captured_at_ms": int(time.time() * 1000),
        "symbol": symbol,
        "mark_price": mark,
        "index_price": index,
        "funding_rate": funding,
        "next_funding_time": next_funding,
        "open_interest": oi,
        "oi_change_pct": round(oi_change, 5) if oi_change is not None else None,
        "taker_ratio": round(taker_ratio, 6) if taker_ratio is not None else None,
        "taker_buy_vol": buy_vol,
        "taker_sell_vol": sell_vol,
        "orderbook_bid_notional_top20": round(bidn, 2),
        "orderbook_ask_notional_top20": round(askn, 2),
        "orderbook_imbalance": round(imbalance, 6),
        "orderbook_bid_walls": walls.get("bid_walls") or [],
        "orderbook_ask_walls": walls.get("ask_walls") or [],
        "price_change_24h_pct": price_change_24h,
        "quote_volume_24h": quote_volume_24h,
        "experimental_score": score,
        "factor_label": "NORMALIZED_PUBLIC_DERIVATIVES_V1" if validated else "PARTIAL_PUBLIC_DERIVATIVES_V1",
        "whale_exchange_flow": None,
        "whale_provider_status": "NOT_CONNECTED",
        "live_execution": False,
        "futures_provider": provider,
        "futures_evidence_validated": validated,
        "validation_contract": "MARK_FUNDING_OI_BOOK_TAKER_FLOW_REQUIRED",
        "sources": sources,
    }


def _okx_capture(atlas, symbol, getter=_get_json):
    base = symbol[:-4] if symbol.endswith("USDT") else symbol
    inst = f"{base}-USDT-SWAP"
    enc = urllib.parse.urlencode
    ua = atlas.UA
    ticker = getter("https://www.okx.com/api/v5/market/ticker?" + enc({"instId": inst}), ua)
    mark_obj = getter("https://www.okx.com/api/v5/public/mark-price?" + enc({"instType": "SWAP", "instId": inst}), ua)
    funding_obj = getter("https://www.okx.com/api/v5/public/funding-rate?" + enc({"instId": inst}), ua)
    oi_obj = getter("https://www.okx.com/api/v5/public/open-interest?" + enc({"instType": "SWAP", "instId": inst}), ua)
    book_obj = getter("https://www.okx.com/api/v5/market/books?" + enc({"instId": inst, "sz": 20}), ua)
    trades_obj = getter("https://www.okx.com/api/v5/market/trades?" + enc({"instId": inst, "limit": 100}), ua)
    for obj in (ticker, mark_obj, funding_obj, oi_obj, book_obj, trades_obj):
        if str(obj.get("code")) != "0":
            raise RuntimeError(f"OKX code={obj.get('code')} msg={obj.get('msg')}")
    t = (ticker.get("data") or [None])[0] or {}
    m = (mark_obj.get("data") or [None])[0] or {}
    f = (funding_obj.get("data") or [None])[0] or {}
    o = (oi_obj.get("data") or [None])[0] or {}
    b = (book_obj.get("data") or [None])[0] or {}
    trades = trades_obj.get("data") or []
    mark = _f(m.get("markPx")) or _f(t.get("last"))
    index = _f(f.get("indexPx")) or mark
    funding = _f(f.get("fundingRate"))
    oi = _f(o.get("oi"))
    ratio, buy, sell = _flow_ratio(trades)
    bids = [[x[0], x[1]] for x in (b.get("bids") or []) if len(x) >= 2]
    asks = [[x[0], x[1]] for x in (b.get("asks") or []) if len(x) >= 2]
    bidn, askn, imbalance, walls = _book_metrics(atlas, bids, asks, mark)
    open24 = _f(t.get("open24h"))
    change = ((mark / open24) - 1) * 100 if mark and open24 else None
    return _snapshot(
        atlas, symbol, "OKX_USDT_SWAP_PUBLIC", mark, index, funding,
        int(f.get("nextFundingTime")) if str(f.get("nextFundingTime") or "").isdigit() else None,
        oi, ratio, buy, sell, bidn, askn, imbalance, walls,
        round(change, 5) if change is not None else None, _f(t.get("volCcy24h")),
        ["OKX public market/ticker", "OKX public mark-price", "OKX public funding-rate", "OKX public open-interest", "OKX public books", "OKX public trades"],
    )


def _bybit_capture(atlas, symbol, getter=_get_json):
    enc = urllib.parse.urlencode
    ua = atlas.UA
    ticker = getter("https://api.bybit.com/v5/market/tickers?" + enc({"category": "linear", "symbol": symbol}), ua)
    book_obj = getter("https://api.bybit.com/v5/market/orderbook?" + enc({"category": "linear", "symbol": symbol, "limit": 25}), ua)
    trades_obj = getter("https://api.bybit.com/v5/market/recent-trade?" + enc({"category": "linear", "symbol": symbol, "limit": 100}), ua)
    for obj in (ticker, book_obj, trades_obj):
        if int(obj.get("retCode", -1)) != 0:
            raise RuntimeError(f"Bybit retCode={obj.get('retCode')} msg={obj.get('retMsg')}")
    t = (((ticker.get("result") or {}).get("list")) or [None])[0] or {}
    b = book_obj.get("result") or {}
    trades = ((trades_obj.get("result") or {}).get("list")) or []
    if not t:
        raise RuntimeError("Bybit instrument not available")
    mark = _f(t.get("markPrice")) or _f(t.get("lastPrice"))
    index = _f(t.get("indexPrice")) or mark
    funding = _f(t.get("fundingRate"))
    oi = _f(t.get("openInterest"))
    normalized_trades = [{"side": x.get("side"), "size": x.get("size")} for x in trades]
    ratio, buy, sell = _flow_ratio(normalized_trades)
    bids = [[x[0], x[1]] for x in (b.get("b") or []) if len(x) >= 2]
    asks = [[x[0], x[1]] for x in (b.get("a") or []) if len(x) >= 2]
    bidn, askn, imbalance, walls = _book_metrics(atlas, bids, asks, mark)
    pct = _f(t.get("price24hPcnt"))
    change = pct * 100 if pct is not None else None
    return _snapshot(
        atlas, symbol, "BYBIT_LINEAR_PUBLIC", mark, index, funding,
        int(t.get("nextFundingTime")) if str(t.get("nextFundingTime") or "").isdigit() else None,
        oi, ratio, buy, sell, bidn, askn, imbalance, walls,
        round(change, 5) if change is not None else None, _f(t.get("turnover24h")),
        ["Bybit public linear tickers", "Bybit public linear orderbook", "Bybit public recent trades"],
    )


def _persist(atlas, snap):
    with atlas.ARCHIVE_LOCK:
        with atlas.ARCHIVE.open("a") as handle:
            handle.write(json.dumps(snap, separators=(",", ":")) + "\n")


def install(atlas):
    if getattr(atlas, "_FUTURES_PROVIDER_CHAIN_INSTALLED", False):
        return getattr(atlas, "FUTURES_PROVIDER_CHAIN_STATE", {})
    original_capture = atlas.capture
    original_handler = atlas.Handler.do_GET
    state = {
        "enabled": True,
        "version": VERSION,
        "providers": list(PROVIDERS),
        "attempts": 0,
        "fallback_successes": 0,
        "fallback_failures": 0,
        "last_provider_by_symbol": {},
        "last_error_by_symbol": {},
    }

    def capture(symbol):
        normalized = str(symbol or "").upper().replace("BINANCE:", "")
        try:
            return original_capture(normalized)
        except Exception as primary:
            if normalized == "HYPEUSDT":
                raise
            state["attempts"] += 1
            errors = []
            for provider_name, fetcher in (("OKX_USDT_SWAP_PUBLIC", _okx_capture), ("BYBIT_LINEAR_PUBLIC", _bybit_capture)):
                try:
                    snap = fetcher(atlas, normalized)
                    if not snap.get("futures_evidence_validated"):
                        raise RuntimeError("normalized derivatives contract incomplete")
                    _persist(atlas, snap)
                    state["fallback_successes"] += 1
                    state["last_provider_by_symbol"][normalized] = provider_name
                    state["last_error_by_symbol"].pop(normalized, None)
                    atlas.MARKET_DATA_STATE["futures"]["last_provider"] = provider_name
                    atlas.MARKET_DATA_STATE["futures"]["last_success_at"] = atlas.now_iso()
                    atlas.MARKET_DATA_STATE["futures"]["last_error"] = None
                    return snap
                except Exception as exc:
                    errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")
            state["fallback_failures"] += 1
            message = f"{normalized} futures provider chain failed; primary={type(primary).__name__}: {primary}; " + " | ".join(errors)
            state["last_error_by_symbol"][normalized] = message
            atlas.MARKET_DATA_STATE["futures"]["last_error"] = message
            raise RuntimeError(message)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/futures-provider/status":
            return self._json({"ok": True, **state, "research_only": True, "live_execution": False}, 200)
        return original_handler(self)

    atlas.capture = capture
    atlas.Handler.do_GET = do_GET
    atlas.FUTURES_PROVIDER_CHAIN_STATE = state
    atlas._FUTURES_PROVIDER_CHAIN_INSTALLED = True
    return state
