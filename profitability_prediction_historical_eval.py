"""Frozen historical evaluation for ATLAS Prediction Engine V1."""
import argparse,json,statistics
import historical_core_4_12h_replay as core
import profitability_prediction_engine as pe

def samples(symbol,days,end_ms,btc=None):
    rows=core.fetch_1h(symbol,days,end_ms); btcrows=core.fetch_1h("BTCUSDT",days,end_ms) if btc is None else btc
    bybtc={x["t"]:i for i,x in enumerate(btcrows)}; out=[]; warm=720
    for i in range(warm,len(rows)-12,4):
        bidx=bybtc.get(rows[i]["t"]); bh=btcrows[:bidx+1] if bidx is not None else None
        a=core.atr(rows[:i+1])
        if not a: continue
        x=pe.features(rows[:i+1],bh); y=pe.label(rows[i]["c"],rows[i+1:i+13],a)
        out.append({"t":rows[i]["t"],"symbol":symbol,"entry":rows[i]["c"],"atr":a,"x":x,"y":y,
                    "future_last":rows[i+12]["c"]})
    return out

def evalset(model,rows,min_conf=.45):
    n=correct=trade_n=0; rs=[]
    cm={}
    for z in rows:
        q=pe.predict(model,z["x"]); pred=q["prediction"]; n+=1; correct+=pred==z["y"]
        cm[pred+"_"+z["y"]]=cm.get(pred+"_"+z["y"],0)+1
        if pred in ("UP","DOWN") and q["confidence"]>=min_conf:
            raw=(z["future_last"]-z["entry"])/z["atr"]; r=raw/1.5 if pred=="UP" else -raw/1.5
            rs.append(max(-1,min(2,r))); trade_n+=1
    wins=[r for r in rs if r>0]; losses=[r for r in rs if r<=0]; gl=abs(sum(losses))
    eq=peak=dd=0
    for r in rs: eq+=r; peak=max(peak,eq); dd=max(dd,peak-eq)
    return {"n":n,"accuracy":round(correct/n,4) if n else None,"trades":trade_n,
      "net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,
      "profit_factor":round(sum(wins)/gl,4) if gl else None,"max_drawdown_r":round(dd,4),
      "confusion":cm}

def main():
    a=argparse.ArgumentParser();a.add_argument("--days",type=int,default=180);a.add_argument("--end-ms",type=int,required=True);args=a.parse_args()
    syms=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]; allx=[]
    for s in syms: allx+=samples(s,args.days,args.end_ms)
    tr,va,ho=pe.chronological_split(allx); model=pe.fit(tr)
    print("ATLAS_PREDICTION_RESULT="+json.dumps({"schema":pe.VERSION,"counts":{"train":len(tr),"validation":len(va),"holdout":len(ho)},
      "validation":evalset(model,va),"holdout":evalset(model,ho),"safety":pe.safety()},sort_keys=True))
if __name__=="__main__":main()
