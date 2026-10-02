"""New-window temporal exam for pre-registered side-specialist."""
import argparse,json,statistics
import historical_core_4_12h_replay as core
import profitability_prediction_engine as pe
import profitability_prediction_historical_eval as old
import profitability_prediction_side_specialist as ss

SYMS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ZECUSDT"]

def metric(rs):
    w=[r for r in rs if r>0];l=[r for r in rs if r<=0];gl=abs(sum(l));eq=peak=dd=0
    for r in rs:eq+=r;peak=max(peak,eq);dd=max(dd,peak-eq)
    return {"trades":len(rs),"net_r":round(sum(rs),4),"avg_r":round(statistics.mean(rs),4) if rs else None,
      "pf":round(sum(w)/gl,4) if gl else None,"dd_r":round(dd,4)}

def main():
    a=argparse.ArgumentParser();a.add_argument("--train-days",type=int,default=180);a.add_argument("--train-end-ms",type=int,required=True);a.add_argument("--exam-end-ms",type=int,required=True);args=a.parse_args()
    train=[]
    for s in SYMS: train+=old.samples(s,args.train_days,args.train_end_ms)
    tr,va,prior_holdout=pe.chronological_split(train); model=pe.fit(tr) # exact frozen V1 fit; no new-window fit
    # new window begins strictly after prior exam end
    days=max(31,int((args.exam_end_ms-args.train_end_ms)/(24*3600*1000))+31)
    new=[]
    for s in SYMS:
        for z in old.samples(s,days,args.exam_end_ms):
            if z["t"]>args.train_end_ms:new.append(z)
    base=[]; specialist=[]
    for z in sorted(new,key=lambda x:x["t"]):
        q=pe.predict(model,z["x"]); q["features"]=z["x"]
        if q["prediction"] in ("UP","DOWN") and q["confidence"]>=.45:
            raw=(z["future_last"]-z["entry"])/z["atr"];r=raw/1.5 if q["prediction"]=="UP" else -raw/1.5;base.append(max(-1,min(2,r)))
        if ss.actionable(q):
            raw=(z["future_last"]-z["entry"])/z["atr"];r=raw/1.5 if q["prediction"]=="UP" else -raw/1.5;specialist.append(max(-1,min(2,r)))
    print("ATLAS_NEW_WINDOW_EXAM="+json.dumps({"schema":ss.VERSION,"window":{"after_ms":args.train_end_ms,"end_ms":args.exam_end_ms,"rows":len(new)},
      "baseline_v1":metric(base),"side_specialist":metric(specialist),"safety":ss.safety()},sort_keys=True))
if __name__=="__main__":main()
