"""ATLAS market-data resilience adapter.

Spot:
- HYPEUSDT: OKX -> Bybit.
- Other ATLAS assets: existing Binance chain -> OKX fallback.

Futures:
- Preserve the existing futures capture as primary.
- For HYPE only, if the primary result is missing or explicitly unvalidated,
  try the same normalized OKX/Bybit derivatives contract used by ATLAS for
  other assets. A fallback is accepted only when the existing validation
  contract marks it ``futures_evidence_validated=True``.
- If no validated CEX contract is available, preserve the primary HYPE result
  (or let the later Hyperliquid reliability fallback handle a primary error).

No scoring, thresholds, forward logic, geometry, or execution rules are changed.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

VERSION = "ATLAS_MARKET_DATA_RESILIENCE_V3"


def _f(value):
    return float(value)


def _get_json(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _okx_symbol(symbol):
    normalized = str(symbol or "").upper().replace("BINANCE:", "")
    if not normalized.endswith("USDT"):
        raise RuntimeError(f"Unsupported OKX spot symbol: {normalized}")
    return normalized[:-4] + "-USDT"


def _okx(symbol, limit, ua):
    inst = _okx_symbol(symbol)
    query = urllib.parse.urlencode({"instId": inst, "bar": "1H", "limit": int(limit)})
    obj = _get_json("https://www.okx.com/api/v5/market/candles?" + query, ua)
    if str(obj.get("code")) != "0":
        raise RuntimeError(f"OKX code={obj.get('code')} msg={obj.get('msg')}")
    rows = obj.get("data") or []
    out = []
    for row in reversed(rows):
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
    required = min(100, int(limit))
    if len(out) < required:
        raise RuntimeError(f"OKX insufficient {inst} candles: {len(out)} < {required}")
    return out[-int(limit):], "www.okx.com"


def _bybit_hype(limit, ua):
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
    for row in reversed(rows):
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
    required = min(100, int(limit))
    if len(out) < required:
        raise RuntimeError(f"Bybit insufficient HYPE candles: {len(out)} < {required}")
    return out[-int(limit):], "api.bybit.com"


def _mark_success(atlas, family, provider):
    state = getattr(atlas, "MARKET_DATA_STATE", {}).get(family)
    if state is not None:
        state["last_provider"] = provider
        state["last_success_at"] = atlas.now_iso()
        state["last_error"] = None


def _mark_error(atlas, family, message):
    state = getattr(atlas, "MARKET_DATA_STATE", {}).get(family)
    if state is not None:
        state["last_error"] = message


def _persist_futures(atlas, snap):
    with atlas.ARCHIVE_LOCK:
        with atlas.ARCHIVE.open("a") as handle:
            handle.write(json.dumps(snap, separators=(",", ":")) + "\n")


def _install_hype_futures_fallback(atlas):
    """Upgrade HYPE to validated futures only when the normal contract passes."""
    try:
        import futures_provider_chain as fpc
    except Exception:
        return {"enabled": False, "reason": "futures_provider_chain_import_failed"}

    original_capture = atlas.capture
    state = {
        "enabled": True,
        "attempts": 0,
        "validated_successes": 0,
        "primary_unvalidated": 0,
        "last_provider": None,
        "last_error": None,
    }

    def capture(symbol):
        normalized = str(symbol or "").upper().replace("BINANCE:", "")
        if normalized != "HYPEUSDT":
            return original_capture(normalized)

        primary = None
        primary_error = None
        try:
            primary = original_capture(normalized)
            if isinstance(primary, dict) and primary.get("futures_evidence_validated") is True:
                return primary
            state["primary_unvalidated"] += 1
        except Exception as exc:
            primary_error = exc

        state["attempts"] += 1
        errors = []
        for provider_name, fetcher in (
            ("OKX_USDT_SWAP_PUBLIC", fpc._okx_capture),
            ("BYBIT_LINEAR_PUBLIC", fpc._bybit_capture),
        ):
            try:
                snap = fetcher(atlas, normalized)
                if not isinstance(snap, dict) or snap.get("futures_evidence_validated") is not True:
                    raise RuntimeError("normalized derivatives validation contract incomplete")
                _persist_futures(atlas, snap)
                state["validated_successes"] += 1
                state["last_provider"] = provider_name
                state["last_error"] = None
                _mark_success(atlas, "futures", provider_name)
                return snap
            except Exception as exc:
                errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")

        state["last_error"] = " | ".join(errors) if errors else "no validated HYPE futures fallback"
        if primary is not None:
            # Keep the honest unvalidated primary evidence instead of fabricating
            # validation. Production scoring already treats it as shadow-only.
            return primary
        if primary_error is not None:
            raise primary_error
        raise RuntimeError(state["last_error"])

    atlas.capture = capture
    atlas.HYPE_FUTURES_VALIDATION_STATE = state
    return state


def install(atlas):
    original_spot_klines = atlas._spot_klines

    def spot_klines(symbol, limit=220):
        normalized = str(symbol or "").upper().replace("BINANCE:", "")

        if normalized == "HYPEUSDT":
            errors = []
            for fetcher in (
                lambda: _okx(normalized, limit, atlas.UA),
                lambda: _bybit_hype(limit, atlas.UA),
            ):
                try:
                    rows, provider = fetcher()
                    _mark_success(atlas, "spot", provider)
                    return rows
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}: {exc}")
            message = "HYPEUSDT spot providers failed: " + " | ".join(errors)
            _mark_error(atlas, "spot", message)
            raise RuntimeError(message)

        try:
            return original_spot_klines(normalized, limit)
        except Exception as primary:
            try:
                rows, provider = _okx(normalized, limit, atlas.UA)
                _mark_success(atlas, "spot", provider)
                return rows
            except Exception as fallback:
                message = (
                    f"{normalized} spot provider chain failed; "
                    f"primary={type(primary).__name__}: {primary}; "
                    f"OKX={type(fallback).__name__}: {fallback}"
                )
                _mark_error(atlas, "spot", message)
                raise RuntimeError(message) from fallback

    atlas._spot_klines = spot_klines
    futures_state = _install_hype_futures_fallback(atlas)
    atlas.HYPE_MARKET_DATA_VERSION = VERSION
    atlas.SPOT_MARKET_DATA_VERSION = VERSION
    return {
        "enabled": True,
        "version": VERSION,
        "hype_symbol": "HYPEUSDT",
        "primary": "existing Binance chain",
        "spot_fallback": "OKX spot",
        "hype_spot_providers": ["OKX", "Bybit"],
        "hype_futures_validation": futures_state,
    }
