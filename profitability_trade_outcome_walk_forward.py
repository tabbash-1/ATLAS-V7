"""Frozen multi-window evaluation of direct trade Expected-R selection."""
import json,statistics
import historical_core_4_12h_replay as core
import profitability_prediction_historical_eval as he
import profitability_prediction_side_specialist as ss
import profitability_trade_outcome_predictor as op
import profitability_trade_outcome_eval as oe
SYMS=oe.SYMS
def met(rows):
 rs=[x["r"] for x in rows];w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=pk=dd=0
 for r in rs:eq+=r;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,"pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}
def run(train_end,exam_end,window_days=1):
 dm,om,ntrain=oe.build_training(train_end);span=max(31,int((exam_end-train_end)/86400000)+31);cand=[]
 for s in SYMS:
  btc=core.fetch_1h("BTCUSDT",span,exam_end)
  for z in [q for q in he.samples(s,span,exam_end,btc) if train_end<q["t"]<=exam_end]:
   q=oe.de.predict(dm,z["x"]);q["features"]=z["x"]
   if not ss.actionable(q):continue
   side=q["prediction"];raw=(z["future_last"]-z["entry"])/z["atr"];r=max(-1,min(2,raw/1.5 if side=="UP" else -raw/1.5))
   oq=op.predict(om,op.vector(z["x"],side,q["confidence"]))
   cand.append({"t":z["t"],"symbol":s,"side":side,"r":r,"ev":oq["expected_r"],"p":oq["p_tp_before_sl"]})
 cand.sort(key=lambda x:x["t"]);step=window_days*86400000;wins=[];start=train_end
 while start<exam_end:
  end=min(start+step,exam_end);b=[x for x in cand if start<x["t"]<=end];e=[x for x in b if x["ev"]>0]
  wins.append({"start_ms":start,"end_ms":end,"baseline":met(b),"positive_ev":met(e)});start=end
 ev=[x for x in cand if x["ev"]>0]
 return {"schema":"ATLAS_OUTCOME_WALK_FORWARD_V1","training_rows":ntrain,"rule":"expected_r>0","windows":wins,
 "aggregate":{"baseline":met(cand),"positive_ev":met(ev)},
 "stability":{"windows":len(wins),"positive_ev_active_windows":sum(1 for w in wins if w["positive_ev"]["n"]>0),
 "positive_ev_profitable_windows":sum(1 for w in wins if w["positive_ev"]["net_r"]>0)},
 "by_side":{s:met([x for x in ev if x["side"]==s]) for s in ("UP","DOWN")},
 "by_symbol":{s:met([x for x in ev if x["symbol"]==s]) for s in SYMS},
 "safety":dict(op.safety(),refit_between_windows=False,ev_rule_frozen=True)}
if __name__=="__main__":print("ATLAS_OUTCOME_WALK_FORWARD="+json.dumps(run(1790485200000,1790920800000,1),sort_keys=True))
