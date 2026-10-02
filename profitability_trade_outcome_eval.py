"""Chronological exam: direction-only vs direct TP-before-SL EV selection."""
import json,statistics
import historical_core_4_12h_replay as core
import profitability_prediction_engine as de
import profitability_prediction_historical_eval as he
import profitability_prediction_side_specialist as ss
import profitability_trade_outcome_predictor as op
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]
def met(rs):
 w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=pk=dd=0
 for r in rs:eq+=r;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,"pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}
def build_training(end):
 allz=[]
 for s in SYMS:allz+=he.samples(s,180,end)
 tr,_,_=de.chronological_split(allz);dm=de.fit(tr);rows=[]
 # outcome model learns only from direction candidates inside training split
 for z in tr:
  q=de.predict(dm,z["x"]);side=q["prediction"]
  if side not in ("UP","DOWN"):continue
  # reconstruct path label unavailable in he sample; use final path proxy only if decisive 2R/-1R cannot be known -> skip here
  raw=(z["future_last"]-z["entry"])/z["atr"]; rr=raw/1.5 if side=="UP" else -raw/1.5
  y=1 if rr>=2 else (0 if rr<=-1 else None)
  if y is not None:rows.append({"x":op.vector(z["x"],side,q["confidence"]),"y":y})
 return dm,op.fit(rows),len(rows)
def run(train_end,exam_end):
 dm,om,ntrain=build_training(train_end);span=max(31,int((exam_end-train_end)/86400000)+31);base=[];ev=[];preds=[]
 for s in SYMS:
  btc=core.fetch_1h("BTCUSDT",span,exam_end)
  for z in [q for q in he.samples(s,span,exam_end,btc) if train_end<q["t"]<=exam_end]:
   q=de.predict(dm,z["x"]);q["features"]=z["x"]
   if not ss.actionable(q):continue
   side=q["prediction"];raw=(z["future_last"]-z["entry"])/z["atr"];r=max(-1,min(2,raw/1.5 if side=="UP" else -raw/1.5));base.append(r)
   oq=op.predict(om,op.vector(z["x"],side,q["confidence"]));preds.append(oq["p_tp_before_sl"])
   if oq["expected_r"]>0:ev.append(r)
 return {"schema":"ATLAS_TRADE_OUTCOME_EXAM_V1","outcome_training_rows":ntrain,"side_specialist":met(base),"positive_ev":met(ev),
 "mean_predicted_p_tp":round(statistics.mean(preds),4) if preds else None,"ev_rule":"expected_r>0","safety":op.safety()}
if __name__=="__main__":print("ATLAS_OUTCOME_EXAM="+json.dumps(run(1790485200000,1790920800000),sort_keys=True))
