"""Frozen multi-window walk-forward exam for Prediction V1 vs Side Specialist."""
from __future__ import annotations
import json,statistics
import profitability_prediction_engine as pe
import profitability_prediction_historical_eval as he
import profitability_prediction_side_specialist as ss
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]

def metric(rs):
 w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=peak=dd=0
 for r in rs:eq+=r;peak=max(peak,eq);dd=max(dd,peak-eq)
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,
 "pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}

def score(model,rows,specialist=False):
 rs=[]
 for z in sorted(rows,key=lambda q:q["t"]):
  q=pe.predict(model,z["x"]);q["features"]=z["x"]
  ok=ss.actionable(q) if specialist else q["prediction"] in ("UP","DOWN") and q["confidence"]>=.45
  if not ok:continue
  raw=(z["future_last"]-z["entry"])/z["atr"];r=raw/1.5 if q["prediction"]=="UP" else -raw/1.5
  rs.append(max(-1,min(2,r)))
 return rs

def run(train_end_ms,exam_end_ms,window_days=7):
 # model is frozen from the original 180-day training universe
 base=[]
 for s in SYMS:base+=he.samples(s,180,train_end_ms)
 tr,_,_=pe.chronological_split(base);model=pe.fit(tr)
 # fetch enough warmup once, then slice into untouched chronological windows
 span=max(31,int((exam_end_ms-train_end_ms)/86400000)+31);future=[]
 for s in SYMS:
  future += [z for z in he.samples(s,span,exam_end_ms) if train_end_ms < z["t"] <= exam_end_ms]
 step=window_days*86400000; windows=[];b_all=[];s_all=[];start=train_end_ms
 while start<exam_end_ms:
  end=min(start+step,exam_end_ms);rows=[z for z in future if start<z["t"]<=end]
  br=score(model,rows,False);sr=score(model,rows,True);b_all+=br;s_all+=sr
  windows.append({"start_ms":start,"end_ms":end,"rows":len(rows),"baseline":metric(br),"specialist":metric(sr)})
  start=end
 return {"schema":"ATLAS_PREDICTION_WALK_FORWARD_V1","window_days":window_days,"windows":windows,
 "aggregate":{"baseline":metric(b_all),"specialist":metric(s_all)},
 "stability":{"windows":len(windows),"specialist_positive_net_windows":sum(1 for w in windows if w["specialist"]["net_r"]>0),
 "specialist_pf_gt_1_windows":sum(1 for w in windows if w["specialist"]["pf"] is not None and w["specialist"]["pf"]>1)},
 "safety":dict(ss.safety(),walk_forward=True,refit_between_windows=False)}

if __name__=="__main__":
 import argparse
 a=argparse.ArgumentParser();a.add_argument("--train-end-ms",type=int,required=True);a.add_argument("--exam-end-ms",type=int,required=True);a.add_argument("--window-days",type=int,default=7);x=a.parse_args()
 print("ATLAS_WALK_FORWARD="+json.dumps(run(x.train_end_ms,x.exam_end_ms,x.window_days),sort_keys=True))
