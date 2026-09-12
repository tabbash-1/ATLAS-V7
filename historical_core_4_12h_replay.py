"""ATLAS CORE 4-12H retrospective replay.

Research-only approximation of the current product thesis. It uses only data
available at each historical decision timestamp and never feeds future candles
into signal construction. It does NOT alter Production and is not equivalent to
forward proof or the exact deployed Production scorer.
"""
from __future__ import annotations

import argparse, json, math, statistics, time, urllib.parse, urllib.request
from dataclasses import dataclass

VERSION = "ATLAS_CORE_4_12H_HISTORICAL_REPLAY_V1"
SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]
THRESHOLD = 68


def fetch_1h(symbol, days):
    need = days * 24 + 300
    out=[]; end=int(time.time()*1000)
    while len(out)<need:
        lim=min(1000, need-len(out))
        q=urllib.parse.urlencode({"symbol":symbol,"interval":"1h","limit":lim,"endTime":end})
        url="https://data-api.binance.vision/api/v3/klines?"+q
        with urllib.request.urlopen(url, timeout=30) as r: data=json.load(r)
        if not data: break
        batch=[{"t":int(k[0]),"o":float(k[1]),"h":float(k[2]),"l":float(k[3]),"c":float(k[4]),"v":float(k[5])} for k in data]
        out=batch+out; end=batch[0]["t"]-1
        if len(batch)<lim: break
        time.sleep(.05)
    ded={x["t"]:x for x in out}
    return [ded[k] for k in sorted(ded)][-need:]


def ema(vals,n):
    if len(vals)<n:return None
    a=2/(n+1); x=sum(vals[:n])/n
    for v in vals[n:]: x=a*v+(1-a)*x
    return x


def rsi(vals,n=14):
    if len(vals)<n+1:return None
    d=[vals[i]-vals[i-1] for i in range(1,len(vals))]
    g=[max(x,0) for x in d[-n:]]; l=[max(-x,0) for x in d[-n:]]
    ag=sum(g)/n; al=sum(l)/n
    if al==0:return 100.0
    rs=ag/al; return 100-(100/(1+rs))


def atr(rows,n=14):
    if len(rows)<n+1:return None
    tr=[]
    for i in range(1,len(rows)):
        p=rows[i-1]["c"]; c=rows[i]
        tr.append(max(c["h"]-c["l"],abs(c["h"]-p),abs(c["l"]-p)))
    return sum(tr[-n:])/n


def resample(rows,hours):
    bucket=hours*3600*1000; out=[]; cur=None
    for r in rows:
        b=(r["t"]//bucket)*bucket
        if cur is None or cur["t"]!=b:
            if cur: out.append(cur)
            cur={"t":b,"o":r["o"],"h":r["h"],"l":r["l"],"c":r["c"],"v":r["v"]}
        else:
            cur["h"]=max(cur["h"],r["h"]);cur["l"]=min(cur["l"],r["l"]);cur["c"]=r["c"];cur["v"]+=r["v"]
    if cur: out.append(cur)
    return out


def direction(rows):
    if len(rows)<55:return None
    cls=[x["c"] for x in rows]
    e20=ema(cls[-55:],20);e50=ema(cls[-55:],50)
    recent=rows[-6:]
    hh=recent[-1]["h"]>max(x["h"] for x in recent[:-1])
    ll=recent[-1]["l"]<min(x["l"] for x in recent[:-1])
    if e20 and e50 and cls[-1]>e20>e50:return "LONG"
    if e20 and e50 and cls[-1]<e20<e50:return "SHORT"
    if hh and cls[-1]>e20:return "LONG"
    if ll and cls[-1]<e20:return "SHORT"
    return None


def signal(hist1h):
    r4=resample(hist1h,4); r12=resample(hist1h,12)
    d4=direction(r4); d12=direction(r12); d1=direction(hist1h)
    if not d4 or d4!=d12:return {"ready":False,"reason":"HTF_CONFLICT","score":None}
    side=d4; score=40
    if d1==side:score+=15
    rs=rsi([x["c"] for x in hist1h])
    if rs is not None and ((side=="LONG" and 52<=rs<=75) or (side=="SHORT" and 25<=rs<=48)):score+=15
    recent4=r4[-8:]
    if side=="LONG" and recent4[-1]["c"]>max(x["h"] for x in recent4[-4:-1]):score+=15
    if side=="SHORT" and recent4[-1]["c"]<min(x["l"] for x in recent4[-4:-1]):score+=15
    vols=[x["v"] for x in hist1h[-25:-1]]
    if vols and hist1h[-1]["v"] >= statistics.mean(vols):score+=15
    if score<THRESHOLD:return {"ready":False,"reason":"SCORE_BELOW_THRESHOLD","score":score,"side":side}
    a=atr(hist1h)
    if not a:return {"ready":False,"reason":"NO_ATR","score":score,"side":side}
    entry=hist1h[-1]["c"]
    stop=entry-1.5*a if side=="LONG" else entry+1.5*a
    target=entry+3*a if side=="LONG" else entry-3*a
    return {"ready":True,"score":score,"side":side,"entry":entry,"stop":stop,"target":target}


def settle(sig,future):
    for c in future[:12]:
        hs=c["l"]<=sig["stop"] if sig["side"]=="LONG" else c["h"]>=sig["stop"]
        ht=c["h"]>=sig["target"] if sig["side"]=="LONG" else c["l"]<=sig["target"]
        if hs and ht:return -1.0,"LOSS_BOTH_STOP_FIRST"
        if hs:return -1.0,"LOSS"
        if ht:return 2.0,"WIN_TP2"
    last=future[min(11,len(future)-1)]["c"]
    risk=abs(sig["entry"]-sig["stop"])
    r=(last-sig["entry"])/risk if sig["side"]=="LONG" else (sig["entry"]-last)/risk
    return max(-1,min(2,r)),"EXPIRED"


def replay_symbol(symbol,days):
    rows=fetch_1h(symbol,days)
    warm=60*12
    trades=[]; blockers={}
    i=warm
    while i < len(rows)-12:
        hist=rows[:i+1]; s=signal(hist)
        if not s["ready"]:
            blockers[s["reason"]]=blockers.get(s["reason"],0)+1; i+=4; continue
        r,out=settle(s,rows[i+1:i+13])
        trades.append({"t":rows[i]["t"],"symbol":symbol,"side":s["side"],"score":s["score"],"r":round(r,4),"outcome":out})
        i+=12
    return trades,blockers


def summary(trades):
    rs=[t["r"] for t in trades]; wins=[x for x in rs if x>0]; losses=[x for x in rs if x<=0]
    gp=sum(wins); gl=abs(sum(losses)); eq=10000.; peak=eq; maxdd=0
    for r in rs:
        eq*=1+0.01*r; peak=max(peak,eq); maxdd=max(maxdd,(peak-eq)/peak*100)
    return {"trades":len(rs),"wins":len(wins),"losses":len(losses),"win_rate_pct":round(100*len(wins)/len(rs),2) if rs else 0,"avg_r":round(statistics.mean(rs),4) if rs else 0,"net_r":round(sum(rs),4),"profit_factor":round(gp/gl,4) if gl else ("INF" if gp else 0),"max_drawdown_pct":round(maxdd,2),"equity_1pct_risk":round(eq,2)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=180);ap.add_argument("--symbols",nargs="*",default=SYMBOLS);a=ap.parse_args()
    alltr=[]; by={}; blockers={}
    for sym in a.symbols:
        t,b=replay_symbol(sym,a.days);alltr+=t;by[sym]=summary(t);blockers[sym]=b
        print(sym,json.dumps(by[sym],sort_keys=True),flush=True)
    result={"schema":VERSION,"research_only":True,"live_execution":False,"can_override_production":False,"forward_proof_equivalent":False,"exact_production_scorer":False,"interpretation":"RETROSPECTIVE_POINT_IN_TIME_THESIS_REPLAY_NOT_FORWARD_PROOF","days":a.days,"threshold":THRESHOLD,"symbols":a.symbols,"assumptions":{"signal_uses_past_and_current_closed_1h_only":True,"entry_reference":"decision close","evaluation_horizon_h":12,"intrabar_both_hit":"STOP_FIRST_CONSERVATIVE","risk_per_trade_pct":1.0,"fees_funding_slippage_included":False,"score_is_theory_proxy_not_exact_production_score":True},"overall":summary(alltr),"by_symbol":by,"blockers":blockers,"sample_trades":alltr[:10]}
    print("ATLAS_REPLAY_RESULT="+json.dumps(result,sort_keys=True))

if __name__=="__main__":main()
