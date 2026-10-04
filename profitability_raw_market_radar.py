"""Independent raw-candle Market Radar. Research shadow only; never creates trades."""
from __future__ import annotations
import statistics
from historical_core_4_12h_replay import ema,rsi,atr,resample,direction
VERSION="ATLAS_RAW_MARKET_RADAR_V1"

def features(rows):
 if len(rows)<220:return {"state":"INSUFFICIENT_DATA","radar_score":0}
 r4=resample(rows,4);r12=resample(rows,12);d4=direction(r4);d12=direction(r12);d1=direction(rows)
 side=d4 if d4 and d4==d12 else None;cl=[x["c"] for x in rows];a=atr(rows);rs=rsi(cl);e20=ema(cl[-55:],20)
 vols=[x["v"] for x in rows[-25:-1]];vr=rows[-1]["v"]/statistics.mean(vols) if vols and statistics.mean(vols)>0 else 0
 mom=(cl[-1]/cl[-5]-1) if len(cl)>=5 else 0
 score=0
 if side:score+=40
 if side and d1==side:score+=15
 if side=="LONG" and rs is not None and rs>=52:score+=15
 if side=="SHORT" and rs is not None and rs<=48:score+=15
 if vr>=1:score+=15
 if side=="LONG" and mom>0:score+=10
 if side=="SHORT" and mom<0:score+=10
 if side and a and e20:
  ext=abs(cl[-1]-e20)/a
  if ext<=1:score+=5
 else:ext=None
 state="ARMED" if score>=70 else "WATCH" if score>=50 else "NO_SETUP"
 return {"side":side or "NONE","state":state,"radar_score":min(100,round(score,2)),"d4":d4,"d12":d12,"d1":d1,"rsi":round(rs,2) if rs is not None else None,"volume_ratio":round(vr,3),"momentum_4h_pct":round(mom*100,3),"extension_atr":round(ext,3) if ext is not None else None}

def build(candles_by_symbol):
 rows={s:features(c) for s,c in candles_by_symbol.items()};btc=rows.get("BTCUSDT",{});btc_side=btc.get("side","NONE")
 ranked=[]
 for s,x in rows.items():
  y={"symbol":s,**x,"btc_context":btc_side}
  if s!="BTCUSDT" and y["side"]=="LONG" and btc_side=="SHORT":y["state"]="BLOCKED_BTC_BREAKDOWN";y["radar_score"]=max(0,y["radar_score"]-30)
  ranked.append(y)
 ranked.sort(key=lambda x:(-x["radar_score"],x["symbol"]))
 return {"schema":VERSION,"btc_context":btc,"ranked_universe":ranked,"top_candidates":[x for x in ranked if x["state"] in ("WATCH","ARMED")][:5],"safety":{"research_only":True,"analysis_only":True,"live_execution":False,"can_create_trade":False,"can_override_production":False,"decision_source_of_truth":"FINAL_TRADE_GATE"}}
