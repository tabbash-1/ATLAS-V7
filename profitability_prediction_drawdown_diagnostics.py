"""Development-only diagnostics for Prediction Engine. Never reads the frozen holdout."""
from __future__ import annotations
import statistics
import profitability_prediction_engine as pe

def trade_rows(model,rows,min_conf=.45):
    out=[]
    for z in rows:
        q=pe.predict(model,z["x"]); pred=q["prediction"]
        if pred not in ("UP","DOWN") or q["confidence"]<min_conf: continue
        raw=(z["future_last"]-z["entry"])/z["atr"]; r=raw/1.5 if pred=="UP" else -raw/1.5
        out.append({"t":z["t"],"symbol":z["symbol"],"side":pred,"confidence":q["confidence"],
          "r":max(-1,min(2,r)),"trend4":z["x"]["trend4"],"trend12":z["x"]["trend12"],
          "btc_rel4":z["x"]["btc_rel4"],"vol_ratio":z["x"]["vol_ratio"]})
    return out

def stats(rows):
    rs=[x["r"] for x in rows]; w=[r for r in rs if r>0]; l=[r for r in rs if r<=0]; gl=abs(sum(l))
    eq=peak=dd=0
    for r in rs: eq+=r;peak=max(peak,eq);dd=max(dd,peak-eq)
    return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,
      "pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}

def report(model,development_rows):
    t=trade_rows(model,development_rows)
    return {"overall":stats(t),
      "by_side":{s:stats([x for x in t if x["side"]==s]) for s in ("UP","DOWN")},
      "by_symbol":{s:stats([x for x in t if x["symbol"]==s]) for s in sorted(set(x["symbol"] for x in t))},
      "by_htf_alignment":{"aligned":stats([x for x in t if (x["side"]=="UP" and x["trend4"]>=0 and x["trend12"]>=0) or (x["side"]=="DOWN" and x["trend4"]<=0 and x["trend12"]<=0)]),
        "opposed":stats([x for x in t if (x["side"]=="UP" and (x["trend4"]<0 or x["trend12"]<0)) or (x["side"]=="DOWN" and (x["trend4"]>0 or x["trend12"]>0))])},
      "contract":{"development_only":True,"holdout_read":False,"production_impact":"NONE"}}
