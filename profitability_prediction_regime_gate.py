"""Independent point-in-time regime gate for Prediction Challenger.

Pre-registered before evaluation. Uses only candles at/before decision time.
It blocks unstable/range transition states and direction-opposed stable regimes.
Research only; never changes Production.
"""
from __future__ import annotations
import market_regime_engine as mre
BLOCK={"TRANSITION","UNSTABLE_HIGH_VOL","RANGE","COMPRESSION","UNKNOWN"}
UP={"TREND_UP","BREAKOUT_UP","VOLATILITY_EXPANSION_UP"}
DOWN={"TREND_DOWN","BREAKDOWN_DOWN","VOLATILITY_EXPANSION_DOWN"}
VERSION="ATLAS_PREDICTION_REGIME_GATE_V1"

def _norm(rows):
 return [{"open":r["o"],"high":r["h"],"low":r["l"],"close":r["c"],"volume":r["v"]} for r in rows]

def state(asset_rows,btc_rows):
 a=mre.classify(_norm(asset_rows));b=mre.classify(_norm(btc_rows))
 return {"asset_regime":a["regime"],"btc_regime":b["regime"],"asset_confidence":a["confidence"],"btc_confidence":b["confidence"]}

def allow(side,regime,is_btc=False):
 ar=regime["asset_regime"];br=regime["btc_regime"]
 if ar in BLOCK or br in {"UNSTABLE_HIGH_VOL","UNKNOWN"}:return False
 if side=="UP":
  if ar in DOWN:return False
  if not is_btc and br in DOWN:return False
  return ar in UP
 if side=="DOWN":
  if ar in UP:return False
  return ar in DOWN
 return False

def safety():return {"research_only":True,"production_impact":"NONE","threshold":68,"point_in_time_only":True,"rule_pre_registered":True}
