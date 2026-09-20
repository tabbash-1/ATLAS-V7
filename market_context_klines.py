"""Explicit spot-kline loader for the 4-12H reasoning lane.

The legacy collector _spot_klines() is intentionally 1H. This module requests an
explicit interval so the Market Context adapter never labels 1H candles as 4H.
Research-only.
"""
from __future__ import annotations
import urllib.parse
import collector_server as atlas

ALLOWED={"1h","4h","12h","1d"}
def load(symbol, interval="4h", limit=220):
 if interval not in ALLOWED: raise ValueError("UNSUPPORTED_INTERVAL")
 path=f'/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={interval}&limit={int(limit)}'
 raw=atlas.get_json_fallback([
  'https://data-api.binance.vision'+path,'https://api-gcp.binance.com'+path,
  'https://api1.binance.com'+path,'https://api2.binance.com'+path,
  'https://api3.binance.com'+path,'https://api4.binance.com'+path,'https://api.binance.com'+path], 'spot')
 if not isinstance(raw,list): raise RuntimeError("INVALID_SPOT_KLINE_PAYLOAD")
 return [{"time":int(x[0]),"open":atlas.fnum(x[1]),"high":atlas.fnum(x[2]),"low":atlas.fnum(x[3]),"close":atlas.fnum(x[4]),"volume":atlas.fnum(x[5]),"interval":interval} for x in raw]
