"""ATLAS disciplined 4-12H short-swing challenger.

Pure evaluator over supplied evidence. Never fetches/invents data and cannot
mutate FINAL_TRADE_GATE. NO_TRADE is fail-closed.
"""
from __future__ import annotations
VERSION="ATLAS_SHORT_SWING_DISCIPLINE_V1_SHADOW"
def n(v):
 try:return float(v)
 except:return None
def evaluate(d):
 d=d or {}; direction=str(d.get("direction") or "").upper()
 conf=[]; blockers=[]
 btc=str(d.get("btc_trend") or "UNKNOWN").upper()
 h4=str(d.get("trend_4h") or "UNKNOWN").upper(); d1=str(d.get("trend_1d") or "UNKNOWN").upper()
 if direction=="LONG" and btc in ("BREAKDOWN","BEARISH_BREAKDOWN"): blockers.append("BTC_BREAKING_DOWN")
 if direction not in ("LONG","SHORT") or h4!=direction or d1!=direction:blockers.append("HTF_NOT_ALIGNED")
 if d.get("structure_confirmed") is True:conf.append("STRUCTURE")
 mom=str(d.get("momentum") or "UNKNOWN").upper()
 if mom==direction:conf.append("MOMENTUM")
 if d.get("volume_above_average") is True:conf.append("VOLUME")
 deriv=str(d.get("derivatives_bias") or "UNKNOWN").upper()
 if deriv==direction:conf.append("DERIVATIVES")
 if d.get("crowded_against_setup") is True:blockers.append("CROWDED_TRADE")
 if d.get("low_liquidity") is True:blockers.append("LOW_LIQUIDITY")
 if d.get("news_driven_spike") is True:blockers.append("NEWS_DRIVEN_SPIKE")
 if d.get("signals_conflict") is True:blockers.append("SIGNAL_CONFLICT")
 if len(set(conf))<3:blockers.append("LT_3_INDEPENDENT_CONFIRMATIONS")
 entry=n(d.get("entry"));sl=n(d.get("sl"));tp1=n(d.get("tp1"));tp2=n(d.get("tp2"))
 rr=n(d.get("net_rr")); confidence=n(d.get("confidence"))
 if None in (entry,sl,tp1,tp2):blockers.append("MISSING_GEOMETRY")
 if str(d.get("sl_basis") or "").upper() not in ("STRUCTURE","ATR_1_5_2_0"):blockers.append("INVALID_SL_BASIS")
 if rr is None or rr<2:blockers.append("NET_RR_LT_2")
 if confidence is None or confidence<70:blockers.append("CONFIDENCE_LT_70")
 risk=n(d.get("position_risk_pct"))
 if risk is None or not 1<=risk<=2:blockers.append("RISK_OUTSIDE_1_2_PCT")
 lev=n(d.get("leverage"))
 if lev is None or lev>3:blockers.append("LEVERAGE_GT_3_OR_MISSING")
 liq=n(d.get("liquidation_price"))
 if direction=="LONG" and liq is not None and sl is not None and liq>=sl:blockers.append("LIQUIDATION_NOT_BEYOND_SL")
 if direction=="SHORT" and liq is not None and sl is not None and liq<=sl:blockers.append("LIQUIDATION_NOT_BEYOND_SL")
 signal=direction if not blockers else "NO_TRADE"
 return {"version":VERSION,"signal":signal,"entry":entry if signal!="NO_TRADE" else None,"sl":sl if signal!="NO_TRADE" else None,
 "tp1":tp1 if signal!="NO_TRADE" else None,"tp2":tp2 if signal!="NO_TRADE" else None,"rr":rr if signal!="NO_TRADE" else None,
 "confidence":confidence or 0,"confirmations":conf,"blockers":blockers,"invalidation":d.get("invalidation"),
 "leverage":lev if signal!="NO_TRADE" else None,"position_risk_pct":risk if signal!="NO_TRADE" else None,
 "reasoning_ar":("الإعداد مستوفٍ لقواعد السوينج القصير 4–12 ساعة." if signal!="NO_TRADE" else "لا توجد صفقة لأن شرطًا أو أكثر من شروط الجودة/المخاطر غير مستوفى."),
 "research_only":True,"production_effect":"NONE","can_override_final_trade_gate":False,"automatic_promotion":False}
