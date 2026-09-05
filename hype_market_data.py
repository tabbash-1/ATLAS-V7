"""ATLAS market-data resilience adapter.

Adds a small in-process spot cache for the web runtime so concurrent decision
requests do not repeatedly hit upstream exchanges. Fresh cache entries are used
for a short TTL; a bounded stale entry may be used only when every live provider
fails. This changes transport reliability only: scoring, thresholds, geometry,
quality gates, and canonical analyst decisions are untouched.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request

VERSION = "ATLAS_MARKET_DATA_RESILIENCE_V4_BOUNDED_CACHE"
CACHE_TTL_SECONDS = 30.0
STALE_IF_ERROR_SECONDS = 300.0
_CACHE = {}
_CACHE_LOCK = threading.RLock()
_KEY_LOCKS = {}
_CACHE_STATE = {"hits": 0, "misses": 0, "live_fetches": 0, "stale_fallbacks": 0, "errors": 0}


def _f(value): return float(value)

def _get_json(url, ua):
    req=urllib.request.Request(url,headers={"User-Agent":ua,"Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))

def _okx_symbol(symbol):
    normalized=str(symbol or "").upper().replace("BINANCE:","")
    if not normalized.endswith("USDT"): raise RuntimeError(f"Unsupported OKX spot symbol: {normalized}")
    return normalized[:-4]+"-USDT"

def _okx(symbol,limit,ua):
    inst=_okx_symbol(symbol); query=urllib.parse.urlencode({"instId":inst,"bar":"1H","limit":int(limit)})
    obj=_get_json("https://www.okx.com/api/v5/market/candles?"+query,ua)
    if str(obj.get("code"))!="0": raise RuntimeError(f"OKX code={obj.get('code')} msg={obj.get('msg')}")
    out=[]
    for row in reversed(obj.get("data") or []):
        if not isinstance(row,list) or len(row)<6: continue
        out.append({"open_time":int(row[0]),"open":_f(row[1]),"high":_f(row[2]),"low":_f(row[3]),"close":_f(row[4]),"volume":_f(row[5])})
    required=min(100,int(limit))
    if len(out)<required: raise RuntimeError(f"OKX insufficient {inst} candles: {len(out)} < {required}")
    return out[-int(limit):],"www.okx.com"

def _bybit_hype(limit,ua):
    query=urllib.parse.urlencode({"category":"spot","symbol":"HYPEUSDT","interval":"60","limit":int(limit)})
    obj=_get_json("https://api.bybit.com/v5/market/kline?"+query,ua)
    if int(obj.get("retCode",-1))!=0: raise RuntimeError(f"Bybit retCode={obj.get('retCode')} msg={obj.get('retMsg')}")
    out=[]
    for row in reversed(((obj.get("result") or {}).get("list") or [])):
        if not isinstance(row,list) or len(row)<6: continue
        out.append({"open_time":int(row[0]),"open":_f(row[1]),"high":_f(row[2]),"low":_f(row[3]),"close":_f(row[4]),"volume":_f(row[5])})
    required=min(100,int(limit))
    if len(out)<required: raise RuntimeError(f"Bybit insufficient HYPE candles: {len(out)} < {required}")
    return out[-int(limit):],"api.bybit.com"

def _mark_success(atlas,family,provider):
    state=getattr(atlas,"MARKET_DATA_STATE",{}).get(family)
    if state is not None:
        state["last_provider"]=provider; state["last_success_at"]=atlas.now_iso(); state["last_error"]=None

def _mark_error(atlas,family,message):
    state=getattr(atlas,"MARKET_DATA_STATE",{}).get(family)
    if state is not None: state["last_error"]=message

def _persist_futures(atlas,snap):
    with atlas.ARCHIVE_LOCK:
        with atlas.ARCHIVE.open("a") as handle: handle.write(json.dumps(snap,separators=(",",":"))+"\n")

def _install_hype_futures_fallback(atlas):
    try: import futures_provider_chain as fpc
    except Exception: return {"enabled":False,"reason":"futures_provider_chain_import_failed"}
    original_capture=atlas.capture
    state={"enabled":True,"attempts":0,"validated_successes":0,"primary_unvalidated":0,"last_provider":None,"last_error":None}
    def capture(symbol):
        normalized=str(symbol or "").upper().replace("BINANCE:","")
        if normalized!="HYPEUSDT": return original_capture(normalized)
        primary=None; primary_error=None
        try:
            primary=original_capture(normalized)
            if isinstance(primary,dict) and primary.get("futures_evidence_validated") is True: return primary
            state["primary_unvalidated"]+=1
        except Exception as exc: primary_error=exc
        state["attempts"]+=1; errors=[]
        for provider_name,fetcher in (("OKX_USDT_SWAP_PUBLIC",fpc._okx_capture),("BYBIT_LINEAR_PUBLIC",fpc._bybit_capture)):
            try:
                snap=fetcher(atlas,normalized)
                if not isinstance(snap,dict) or snap.get("futures_evidence_validated") is not True: raise RuntimeError("normalized derivatives validation contract incomplete")
                _persist_futures(atlas,snap); state["validated_successes"]+=1; state["last_provider"]=provider_name; state["last_error"]=None
                _mark_success(atlas,"futures",provider_name); return snap
            except Exception as exc: errors.append(f"{provider_name}: {type(exc).__name__}: {exc}")
        state["last_error"]=" | ".join(errors) if errors else "no validated HYPE futures fallback"
        if primary is not None: return primary
        if primary_error is not None: raise primary_error
        raise RuntimeError(state["last_error"])
    atlas.capture=capture; atlas.HYPE_FUTURES_VALIDATION_STATE=state; return state

def _cache_key(symbol,limit): return (str(symbol).upper(),int(limit))

def _key_lock(key):
    with _CACHE_LOCK: return _KEY_LOCKS.setdefault(key,threading.Lock())

def _cached(key,max_age):
    with _CACHE_LOCK:
        item=_CACHE.get(key)
        if not item: return None
        if time.monotonic()-item["stored"]<=max_age: return list(item["rows"])
        return None

def _store(key,rows):
    with _CACHE_LOCK: _CACHE[key]={"stored":time.monotonic(),"rows":list(rows)}

def install(atlas):
    original_spot_klines=atlas._spot_klines
    def live_fetch(normalized,limit):
        if normalized=="HYPEUSDT":
            errors=[]
            for fetcher in (lambda:_okx(normalized,limit,atlas.UA),lambda:_bybit_hype(limit,atlas.UA)):
                try:
                    rows,provider=fetcher(); _mark_success(atlas,"spot",provider); return rows
                except Exception as exc: errors.append(f"{type(exc).__name__}: {exc}")
            raise RuntimeError("HYPEUSDT spot providers failed: "+" | ".join(errors))
        try: return original_spot_klines(normalized,limit)
        except Exception as primary:
            try:
                rows,provider=_okx(normalized,limit,atlas.UA); _mark_success(atlas,"spot",provider); return rows
            except Exception as fallback:
                raise RuntimeError(f"{normalized} spot provider chain failed; primary={type(primary).__name__}: {primary}; OKX={type(fallback).__name__}: {fallback}") from fallback
    def spot_klines(symbol,limit=220):
        normalized=str(symbol or "").upper().replace("BINANCE:",""); key=_cache_key(normalized,limit)
        fresh=_cached(key,CACHE_TTL_SECONDS)
        if fresh is not None:
            _CACHE_STATE["hits"]+=1; return fresh
        _CACHE_STATE["misses"]+=1
        with _key_lock(key):
            fresh=_cached(key,CACHE_TTL_SECONDS)
            if fresh is not None:
                _CACHE_STATE["hits"]+=1; return fresh
            try:
                _CACHE_STATE["live_fetches"]+=1; rows=live_fetch(normalized,limit); _store(key,rows); return list(rows)
            except Exception as exc:
                stale=_cached(key,STALE_IF_ERROR_SECONDS)
                if stale is not None:
                    _CACHE_STATE["stale_fallbacks"]+=1
                    _mark_error(atlas,"spot",f"LIVE_FETCH_FAILED_USING_BOUNDED_STALE_CACHE: {type(exc).__name__}: {exc}")
                    return stale
                _CACHE_STATE["errors"]+=1; _mark_error(atlas,"spot",str(exc)); raise
    atlas._spot_klines=spot_klines
    futures_state=_install_hype_futures_fallback(atlas)
    atlas.HYPE_MARKET_DATA_VERSION=VERSION; atlas.SPOT_MARKET_DATA_VERSION=VERSION
    atlas.MARKET_DATA_CACHE_STATE=_CACHE_STATE
    atlas.MARKET_DATA_CACHE_POLICY={"ttl_seconds":CACHE_TTL_SECONDS,"stale_if_error_seconds":STALE_IF_ERROR_SECONDS,"changes_scoring":False,"changes_threshold":False,"live_execution":False}
    return {"enabled":True,"version":VERSION,"cache_policy":atlas.MARKET_DATA_CACHE_POLICY,"hype_symbol":"HYPEUSDT","primary":"existing Binance chain","spot_fallback":"OKX spot","hype_spot_providers":["OKX","Bybit"],"hype_futures_validation":futures_state}
