"""Frozen comparison: V1 vs Side Specialist vs Side+Regime Gate."""
import json,statistics
import profitability_prediction_engine as pe
import profitability_prediction_historical_eval as he
import profitability_prediction_side_specialist as ss
import profitability_prediction_regime_gate as rg
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]
def met(rs):
 w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=pk=dd=0
 for r in rs:eq+=r;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,"pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}
def run(train_end,exam_end):
 train=[]
 for s in SYMS:train+=he.samples(s,180,train_end)
 tr,_,_=pe.chronological_split(train);model=pe.fit(tr)
 span=max(31,int((exam_end-train_end)/86400000)+31); data={}; btc=None
 for s in SYMS:data[s]=he.core.fetch_1h(s,span,exam_end)
 btc=data["BTCUSDT"]; out={"baseline":[],"specialist":[],"regime":[]}; bybtc={x["t"]:i for i,x in enumerate(btc)}
 for s in SYMS:
  rows=data[s]; by={x["t"]:i for i,x in enumerate(rows)}
  zs=[z for z in he.samples(s,span,exam_end,btc) if train_end<z["t"]<=exam_end]
  for z in zs:
   q=pe.predict(model,z["x"]);q["features"]=z["x"]; pred=q["prediction"]
   raw=(z["future_last"]-z["entry"])/z["atr"];r=max(-1,min(2,raw/1.5 if pred=="UP" else -raw/1.5))
   if pred in ("UP","DOWN") and q["confidence"]>=.45:out["baseline"].append(r)
   if ss.actionable(q):
    out["specialist"].append(r)
    i=by.get(z["t"]);bi=bybtc.get(z["t"])
    if i is not None and bi is not None:
     st=rg.state(rows[:i+1],btc[:bi+1])
     if rg.allow(pred,st,s=="BTCUSDT"):out["regime"].append(r)
 return {"schema":"ATLAS_PREDICTION_REGIME_COMPARISON_V1","window":{"after_ms":train_end,"end_ms":exam_end},
 "baseline":met(out["baseline"]),"specialist":met(out["specialist"]),"specialist_regime":met(out["regime"]),"safety":rg.safety()}
if __name__=="__main__":
 print("ATLAS_REGIME_EXAM="+json.dumps(run(1790485200000,1790920800000),sort_keys=True))
