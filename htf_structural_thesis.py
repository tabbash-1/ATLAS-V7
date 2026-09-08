"""ATLAS hierarchical 4-12H structural thesis gate.

4H+12H remain direction authority. The frame analyst separates structural trend
from current phase and adds deterministic price-action, candle, momentum,
volume, location and liquidity evidence. No score/threshold changes; no orders.
"""
from __future__ import annotations
import urllib.parse

VERSION="HTF_STRUCTURAL_THESIS_V3_MARKET_INTELLIGENCE"
ANALYSIS_MODEL_VERSION="ATLAS_MARKET_INTELLIGENCE_V1"
PRODUCT_HORIZON="4-12H"
TIMEFRAMES=("1h","4h","12h","1d")
AUTHORITY_TIMEFRAMES=("12h","4h")

def _f(v,default=None):
    try:return float(v)
    except Exception:return default

def _ema(vals,n):
    vals=[float(x) for x in vals if x is not None]
    if not vals:return None
    k=2.0/(n+1.0); out=vals[0]
    for v in vals[1:]:out=v*k+out*(1-k)
    return out

def _atr(rows,n=14):
    if len(rows)<=n:return None
    trs=[]
    for i in range(len(rows)-n,len(rows)):
        h=_f(rows[i].get("high"));l=_f(rows[i].get("low"));pc=_f(rows[i-1].get("close"))
        if None not in (h,l,pc):trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs)/len(trs) if trs else None

def _rsi(vals,n=14):
    if len(vals)<=n:return None
    d=[vals[i]-vals[i-1] for i in range(len(vals)-n,len(vals))]
    g=sum(max(x,0) for x in d)/n;l=sum(max(-x,0) for x in d)/n
    if l==0:return 100.0
    return 100-(100/(1+g/l))

def _swings(rows,left=2,right=2):
    highs,lows=[],[]
    for i in range(left,len(rows)-right):
        h=_f(rows[i].get("high"));l=_f(rows[i].get("low"))
        if h is not None and all(h>=_f(rows[j].get("high"),h) for j in range(i-left,i+right+1) if j!=i):highs.append({"index":i,"price":h,"time":rows[i].get("time")})
        if l is not None and all(l<=_f(rows[j].get("low"),l) for j in range(i-left,i+right+1) if j!=i):lows.append({"index":i,"price":l,"time":rows[i].get("time")})
    return highs,lows

def _structure_bias(highs,lows):
    if len(highs)<2 or len(lows)<2:return "NEUTRAL","INSUFFICIENT_SWINGS"
    h0,h1=highs[-2]["price"],highs[-1]["price"];l0,l1=lows[-2]["price"],lows[-1]["price"]
    if h1>h0 and l1>l0:return "LONG","HH_HL"
    if h1<h0 and l1<l0:return "SHORT","LH_LL"
    return "NEUTRAL","MIXED_STRUCTURE"

def _candle_state(rows,atr):
    r=rows[-1];p=rows[-2]
    o,h,l,c=map(lambda k:_f(r.get(k)),("open","high","low","close"));po,pc=_f(p.get("open")),_f(p.get("close"))
    if None in (o,h,l,c):return {"pattern":"UNKNOWN","direction":"NEUTRAL"}
    rng=max(h-l,1e-12);body=abs(c-o);upper=h-max(o,c);lower=min(o,c)-l
    pattern="NORMAL"
    if body/rng<=.12:pattern="DOJI"
    elif lower/rng>=.55 and body/rng<=.4:pattern="HAMMER_REJECTION"
    elif upper/rng>=.55 and body/rng<=.4:pattern="SHOOTING_STAR_REJECTION"
    elif po is not None and pc is not None and c>o and pc<po and o<=pc and c>=po:pattern="BULLISH_ENGULFING"
    elif po is not None and pc is not None and c<o and pc>po and o>=pc and c<=po:pattern="BEARISH_ENGULFING"
    elif atr and body>=1.1*atr:pattern="BULLISH_DISPLACEMENT" if c>o else "BEARISH_DISPLACEMENT"
    direction="BULLISH" if c>o else "BEARISH" if c<o else "NEUTRAL"
    return {"pattern":pattern,"direction":direction,"body_to_range":round(body/rng,3),"upper_wick_to_range":round(upper/rng,3),"lower_wick_to_range":round(lower/rng,3)}

def _phase(rows,closes,structural,atr):
    px=closes[-1];e8=_ema(closes[-40:],8);e20=_ema(closes[-80:],20);old=_ema(closes[-43:-3],8) if len(closes)>=43 else None
    r3=px/closes[-4]-1 if len(closes)>=4 and closes[-4] else 0;r6=px/closes[-7]-1 if len(closes)>=7 and closes[-7] else 0;ap=atr/px if atr and px else 0
    impulse="NEUTRAL"
    if e8 is not None and e20 is not None:
        if px<e8<e20 and r3<0:impulse="BEARISH"
        elif px>e8>e20 and r3>0:impulse="BULLISH"
        elif r3<-max(ap,.003):impulse="BEARISH"
        elif r3>max(ap,.003):impulse="BULLISH"
    slope="RISING" if e8 is not None and old is not None and e8>old else "FALLING" if e8 is not None and old is not None and e8<old else "FLAT"
    vols=[_f(x.get("volume")) for x in rows[-21:]];vols=[v for v in vols if v is not None and v>=0];rv=None
    if len(vols)>=6:
        base=sum(vols[:-1])/len(vols[:-1]);rv=vols[-1]/base if base>0 else None
    phase="BEARISH_CORRECTION" if structural=="LONG" and impulse=="BEARISH" else "BULLISH_CORRECTION" if structural=="SHORT" and impulse=="BULLISH" else "BULLISH_EXPANSION" if impulse=="BULLISH" else "BEARISH_EXPANSION" if impulse=="BEARISH" else "CONSOLIDATION_OR_TRANSITION"
    health="DETERIORATING" if (structural=="LONG" and impulse=="BEARISH") or (structural=="SHORT" and impulse=="BULLISH") else "CONFIRMED" if (structural=="LONG" and impulse=="BULLISH") or (structural=="SHORT" and impulse=="BEARISH") else "STABLE"
    return {"current_phase":phase,"impulse":impulse,"momentum_slope":slope,"trend_health":health,"return_3_bars_pct":round(r3*100,4),"return_6_bars_pct":round(r6*100,4),"ema8":round(e8,10) if e8 is not None else None,"relative_volume":round(rv,3) if rv is not None else None,"volume_state":"EXPANDING" if rv and rv>=1.35 else "CONTRACTING" if rv and rv<=.7 else "NORMAL" if rv is not None else "UNKNOWN"}

def analyze_frame(rows,timeframe):
    rows=list(rows or [])
    if len(rows)<60:return {"timeframe":timeframe,"ok":False,"bias":"UNKNOWN","reason":"INSUFFICIENT_CANDLES","candles":len(rows)}
    closes=[_f(x.get("close")) for x in rows];closes=[x for x in closes if x is not None]
    if len(closes)<60:return {"timeframe":timeframe,"ok":False,"bias":"UNKNOWN","reason":"INVALID_CANDLES","candles":len(closes)}
    px=closes[-1];e20=_ema(closes[-100:],20);e50=_ema(closes[-160:],50);highs,lows=_swings(rows[-160:]);sb,structure=_structure_bias(highs,lows)
    trend="LONG" if e20 is not None and e50 is not None and px>e20>e50 else "SHORT" if e20 is not None and e50 is not None and px<e20<e50 else "NEUTRAL"
    if sb==trend and sb in ("LONG","SHORT"):bias,conf=sb,"STRONG"
    elif sb in ("LONG","SHORT") and trend=="NEUTRAL":bias,conf=sb,"STRUCTURE"
    elif trend in ("LONG","SHORT") and sb=="NEUTRAL":bias,conf=trend,"TREND_ONLY"
    else:bias,conf="NEUTRAL","CONFLICT"
    sh=highs[-1]["price"] if highs else None;sl=lows[-1]["price"] if lows else None
    breakout="BREAKOUT_UP" if sh is not None and px>sh else "BREAKDOWN_DOWN" if sl is not None and px<sl else "NONE"
    atr=_atr(rows);out={"timeframe":timeframe,"ok":True,"bias":bias,"structural_direction":bias,"confidence":conf,"structure":structure,"trend":trend,"price":px,"ema20":round(e20,10) if e20 is not None else None,"ema50":round(e50,10) if e50 is not None else None,"atr14":round(atr,10) if atr else None,"rsi14":round(_rsi(closes),2) if _rsi(closes) is not None else None,"last_swing_high":sh,"last_swing_low":sl,"breakout_state":breakout,"analysis_model_version":ANALYSIS_MODEL_VERSION}
    out.update(_phase(rows,closes,bias,atr));out["candle"]=_candle_state(rows,atr)
    if sh is not None and sl is not None and sh>sl:
        loc=(px-sl)/(sh-sl);out["range_location_pct"]=round(loc*100,2);out["price_location"]="NEAR_SUPPORT" if loc<=.2 else "NEAR_RESISTANCE" if loc>=.8 else "MID_RANGE"
    else:out["range_location_pct"]=None;out["price_location"]="UNKNOWN"
    out["structure_event"]="BOS_UP" if breakout=="BREAKOUT_UP" and bias=="LONG" else "BOS_DOWN" if breakout=="BREAKDOWN_DOWN" and bias=="SHORT" else "POTENTIAL_CHOCH_UP" if breakout=="BREAKOUT_UP" and bias=="SHORT" else "POTENTIAL_CHOCH_DOWN" if breakout=="BREAKDOWN_DOWN" and bias=="LONG" else "NONE"
    return out

def _nearest_levels(states,px):
    sup,res=[],[]
    for tf in ("4h","12h","1d"):
        s=states.get(tf) or {}
        for k in ("last_swing_low","last_swing_high","ema20","ema50"):
            v=_f(s.get(k))
            if not v or v<=0:continue
            item={"price":v,"timeframe":tf,"source":k.upper()}
            (sup if v<px else res).append(item)
    sup.sort(key=lambda x:x["price"],reverse=True);res.sort(key=lambda x:x["price"])
    return (sup[0] if sup else None),(res[0] if res else None)

def analyze_frames(frames,proposed_direction=None):
    states={tf:analyze_frame(frames.get(tf) or [],tf) for tf in TIMEFRAMES};missing=[tf for tf in TIMEFRAMES if not states[tf].get("ok")]
    if missing:return {"version":VERSION,"analysis_model_version":ANALYSIS_MODEL_VERSION,"status":"BLOCK","direction":None,"product_direction":None,"entry_confirmation_direction":proposed_direction,"direction_alignment":"UNKNOWN","reason":"HTF_DATA_INCOMPLETE","missing_timeframes":missing,"frames":states,"product_horizon":PRODUCT_HORIZON,"can_flip_from_1h_only":False,"live_execution":False}
    b4,b12,b1,bd=(states[x]["bias"] for x in ("4h","12h","1h","1d"));direction=None
    if b4 not in ("LONG","SHORT") or b12 not in ("LONG","SHORT") or b4!=b12:status,reason="WAIT","4H_12H_NOT_ALIGNED"
    else:
        direction=b4;counter4=states["4h"].get("impulse") not in ("NEUTRAL","BULLISH" if direction=="LONG" else "BEARISH")
        daily=bd in ("LONG","SHORT") and bd!=direction and states["1d"].get("confidence")=="STRONG"
        if daily:status,reason="WAIT","1D_MACRO_STRONGLY_OPPOSES_HTF"
        elif counter4 and states["4h"].get("volume_state")=="EXPANDING":status,reason="WAIT","4H_COUNTER_IMPULSE_WITH_VOLUME"
        elif proposed_direction in ("LONG","SHORT") and proposed_direction!=direction:status,reason="WAIT","ENTRY_CONFIRMATION_OPPOSES_PRODUCT_DIRECTION"
        elif b1 in ("LONG","SHORT") and b1!=direction:status,reason="WAIT","1H_NOT_CONFIRMED_HTF"
        else:status,reason="PASS","HTF_ALIGNED_CURRENT_PHASE_ACCEPTABLE"
    px=_f(states["1h"].get("price"));support,resistance=_nearest_levels(states,px) if px else (None,None)
    inv=support if direction=="LONG" else resistance if direction=="SHORT" else None;level=_f(states["4h"].get("last_swing_high" if direction=="LONG" else "last_swing_low")) if direction else None
    trigger="Wait for 4H and 12H structural alignment" if not direction else f"1H confirms {direction}; 4H phase must not show expanding counter-impulse"
    alignment="NO_PRODUCT_DIRECTION" if not direction else "NO_ENTRY_CONFIRMATION_DIRECTION" if proposed_direction not in ("LONG","SHORT") else "ALIGNED" if proposed_direction==direction else "OPPOSED"
    thesis={"version":VERSION,"analysis_model_version":ANALYSIS_MODEL_VERSION,"status":status,"direction":direction,"product_direction":direction,"entry_confirmation_direction":proposed_direction,"direction_alignment":alignment,"reason":reason,"product_horizon":PRODUCT_HORIZON,"authority_timeframes":list(AUTHORITY_TIMEFRAMES),"context_timeframe":"1d","confirmation_timeframe":"1h","daily_context":bd,"daily_context_confidence":states["1d"].get("confidence"),"frames":states,"nearest_support":support,"nearest_resistance":resistance,"trigger":trigger,"trigger_level":level,"invalidation_level":inv.get("price") if inv else None,"invalidation_source":inv,"can_flip_from_1h_only":False,"score_changed":False,"threshold_changed":False,"research_only":False,"analysis_only":True,"live_execution":False}
    thesis["market_thesis"]={"macro":bd,"swing_structure":b12,"primary_structure":b4,"primary_phase":states["4h"].get("current_phase"),"entry_impulse":states["1h"].get("impulse"),"momentum":states["4h"].get("momentum_slope"),"volume":states["4h"].get("volume_state"),"price_location":states["4h"].get("price_location"),"candle":states["4h"].get("candle"),"structure_event":states["4h"].get("structure_event"),"support":support,"resistance":resistance,"primary_scenario":direction or "WAIT_FOR_ALIGNMENT","confirmation":trigger,"invalidation":thesis["invalidation_level"]}
    return thesis

def _fetch_klines(atlas,symbol,interval,limit=220):
    path=f"/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={urllib.parse.quote(interval)}&limit={int(limit)}";urls=[x+path for x in ("https://data-api.binance.vision","https://api-gcp.binance.com","https://api1.binance.com","https://api2.binance.com","https://api3.binance.com","https://api4.binance.com","https://api.binance.com")];raw=atlas.get_json_fallback(urls,"spot")
    if not isinstance(raw,list):raise RuntimeError(f"Invalid {interval} kline payload")
    return [{"time":int(x[0]),"open":_f(x[1]),"high":_f(x[2]),"low":_f(x[3]),"close":_f(x[4]),"volume":_f(x[5])} for x in raw]

def build_live_thesis(atlas,symbol,proposed_direction=None):
    frames={};errors={}
    for tf in TIMEFRAMES:
        try:frames[tf]=atlas._spot_klines(symbol,220) if tf=="1h" else _fetch_klines(atlas,symbol,tf,220)
        except Exception as exc:frames[tf]=[];errors[tf]=f"{type(exc).__name__}: {exc}"
    t=analyze_frames(frames,proposed_direction);t["symbol"]=symbol;t["fetch_errors"]=errors;return t

def install(atlas):
    if getattr(atlas,"_HTF_STRUCTURAL_THESIS_INSTALLED",False):return getattr(atlas,"HTF_STRUCTURAL_THESIS_STATE",{"enabled":True,"version":VERSION})
    original=atlas.production_decision
    def wrapped(symbol):
        row=original(symbol)
        if not isinstance(row,dict) or not row.get("ok"):return row
        proposed=row.get("candidate_direction");t=build_live_thesis(atlas,str(symbol or row.get("symbol") or "").upper().replace("BINANCE:",""));pd=t.get("product_direction") if t.get("product_direction") in ("LONG","SHORT") else None
        row["htf_thesis"]=t;row["htf_thesis_version"]=VERSION;row["htf_analysis_model_version"]=ANALYSIS_MODEL_VERSION;row["market_thesis"]=t.get("market_thesis");row["product_direction"]=pd;row["entry_confirmation_direction"]=proposed if proposed in ("LONG","SHORT") else None;row["direction_alignment"]="ALIGNED" if pd and proposed==pd else "OPPOSED" if pd and proposed in ("LONG","SHORT") else "NO_PRODUCT_DIRECTION" if not pd else "NO_ENTRY_CONFIRMATION_DIRECTION";row["direction_authority"]="HTF_12H_4H";row["htf_score_preserved"]=True;row["htf_threshold_preserved"]=True
        if t.get("status")!="PASS":row["pre_htf_actionable_decision"]=row.get("actionable_decision");row["actionable_decision"]="WAIT";row["actionable_reason"]="HTF_"+str(t.get("reason") or "NOT_ALIGNED");row["analysis_ready"]=False;row["setup_ready"]=False;row["can_execute"]=False
        return row
    atlas.production_decision=wrapped;atlas._HTF_STRUCTURAL_THESIS_INSTALLED=True;state={"enabled":True,"version":VERSION,"analysis_model_version":ANALYSIS_MODEL_VERSION,"product_horizon":PRODUCT_HORIZON,"authority_timeframes":list(AUTHORITY_TIMEFRAMES),"score_changed":False,"threshold_changed":False,"analysis_only":True,"live_execution":False};atlas.HTF_STRUCTURAL_THESIS_STATE=state;return state
