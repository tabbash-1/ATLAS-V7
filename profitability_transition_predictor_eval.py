"""Strict chronological transition-prediction exam + side-specialist overlay."""
import json,statistics
import historical_core_4_12h_replay as core
import profitability_prediction_engine as de
import profitability_prediction_historical_eval as he
import profitability_prediction_side_specialist as ss
import profitability_transition_predictor as tp
SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]
def metric(rs):
 w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=pk=dd=0
 for r in rs:eq+=r;pk=max(pk,eq);dd=max(dd,pk-eq)
 return {"n":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,"pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}
def dataset(days,end):
 out=[]
 for s in SYMS:
  rows=core.fetch_1h(s,days,end)
  for i in range(720,len(rows)-12,4):
   a=core.atr(rows[:i+1])
   if a:out.append({"t":rows[i]["t"],"symbol":s,"x":tp.features(rows[:i+1]),"y":tp.label(rows[i]["c"],rows[i+1:i+13],a)})
 return sorted(out,key=lambda z:z["t"])
def run(train_end,exam_end):
 ds=dataset(180,train_end);cut=int(len(ds)*.6);tm=tp.fit(ds[:cut])
 dtrain=[]
 for s in SYMS:dtrain+=he.samples(s,180,train_end)
 tr,_,_=de.chronological_split(dtrain);dm=de.fit(tr)
 span=max(31,int((exam_end-train_end)/86400000)+31);rows=[];transition_correct=transition_n=0;base=[];overlay=[]
 for s in SYMS:
  raw=core.fetch_1h(s,span,exam_end)
  btc=core.fetch_1h("BTCUSDT",span,exam_end)
  for z in [q for q in he.samples(s,span,exam_end,btc) if train_end<q["t"]<=exam_end]:
   idx=next((i for i,x in enumerate(raw) if x["t"]==z["t"]),None)
   if idx is None:continue
   tq=tp.predict(tm,tp.features(raw[:idx+1])); transition_n+=1
   # label only for evaluation, never input to predictor
   actual=tp.label(z["entry"],raw[idx+1:idx+13],z["atr"]);transition_correct+=tq["prediction"]==actual
   dq=de.predict(dm,z["x"]);dq["features"]=z["x"]
   if not ss.actionable(dq):continue
   pred=dq["prediction"];rawr=(z["future_last"]-z["entry"])/z["atr"];r=max(-1,min(2,rawr/1.5 if pred=="UP" else -rawr/1.5));base.append(r)
   p=tq["probabilities"].get("EXPAND_UP" if pred=="UP" else "EXPAND_DOWN",0)
   # preregistered permissive transition evidence, not stable-regime confirmation
   if p>=.30:overlay.append(r)
 return {"schema":"ATLAS_TRANSITION_PREDICTOR_EXAM_V1","transition":{"n":transition_n,"accuracy":round(transition_correct/transition_n,4) if transition_n else None},
 "side_specialist":metric(base),"transition_overlay":metric(overlay),"overlay_min_directional_expansion_p":.30,"safety":tp.safety()}
if __name__=="__main__":print("ATLAS_TRANSITION_EXAM="+json.dumps(run(1790485200000,1790920800000),sort_keys=True))
