"""ATLAS probabilistic direction challenger.

Point-in-time features -> P(UP/DOWN/RANGE) for 4-12H. Research only.
The future horizon is used solely to create labels after features are frozen.
No Production score/threshold is changed.
"""
from __future__ import annotations
import math, statistics
from historical_core_4_12h_replay import ema,rsi,atr,resample

VERSION="ATLAS_PREDICTION_ENGINE_V1"
FEATURES=("ret1","ret4","ret12","rsi14","ema20_dist_atr","vol_ratio","range_atr","trend4","trend12","btc_rel4")

def _ret(rows,n):
    return rows[-1]["c"]/rows[-1-n]["c"]-1 if len(rows)>n else 0.0
def _z(v,m,s): return (v-m)/s if s>1e-12 else 0.0
def features(rows,btc_rows=None):
    a=atr(rows) or 1e-12; c=rows[-1]["c"]; e=ema([x["c"] for x in rows[-80:]],20) or c
    vols=[x["v"] for x in rows[-25:-1]]; vm=statistics.mean(vols) if vols else rows[-1]["v"]
    r4=resample(rows,4); r12=resample(rows,12)
    def tr(rs):
        if len(rs)<6:return 0.0
        e1=ema([x["c"] for x in rs[-20:]],5); e2=ema([x["c"] for x in rs[-30:]],10)
        return 1.0 if e1 and e2 and rs[-1]["c"]>e1>e2 else (-1.0 if e1 and e2 and rs[-1]["c"]<e1<e2 else 0.0)
    rel=_ret(rows,4)-(_ret(btc_rows,4) if btc_rows else 0.0)
    return {"ret1":_ret(rows,1),"ret4":_ret(rows,4),"ret12":_ret(rows,12),
      "rsi14":((rsi([x["c"] for x in rows]) or 50)-50)/50,
      "ema20_dist_atr":(c-e)/a,"vol_ratio":rows[-1]["v"]/vm-1 if vm else 0,
      "range_atr":(rows[-1]["h"]-rows[-1]["l"])/a,"trend4":tr(r4),"trend12":tr(r12),"btc_rel4":rel}

def label(entry,future,a,move_atr=.75):
    last=future[min(11,len(future)-1)]["c"]; move=(last-entry)/a
    return "UP" if move>=move_atr else ("DOWN" if move<=-move_atr else "RANGE")

def fit(samples):
    # Gaussian Naive Bayes: deterministic, auditable, dependency-free.
    classes=("UP","DOWN","RANGE"); priors={}; stats={}
    for y in classes:
        xs=[x for x in samples if x["y"]==y]; priors[y]=max(len(xs),1)/max(len(samples),1); stats[y]={}
        for f in FEATURES:
            vals=[float(x["x"][f]) for x in xs] or [0.0]
            stats[y][f]=(statistics.mean(vals), max(statistics.pstdev(vals),1e-6))
    return {"priors":priors,"stats":stats}
def predict(model,x):
    scores={}
    for y in ("UP","DOWN","RANGE"):
        s=math.log(model["priors"][y])
        for f in FEATURES:
            m,sd=model["stats"][y][f]; z=_z(float(x[f]),m,sd); s+=-math.log(sd)-.5*z*z
        scores[y]=s
    mx=max(scores.values()); ex={k:math.exp(v-mx) for k,v in scores.items()}; den=sum(ex.values())
    p={k:ex[k]/den for k in ex}; y=max(p,key=p.get)
    return {"prediction":y,"probabilities":{k:round(v,6) for k,v in p.items()},"confidence":round(p[y],6)}

def chronological_split(samples):
    s=sorted(samples,key=lambda x:x["t"]); n=len(s)
    a=int(n*.60); b=int(n*.80)
    return s[:a],s[a:b],s[b:]

def safety():
    return {"research_only":True,"live_execution":False,"production_impact":"NONE","threshold":68,
      "future_features_allowed":False,"holdout_used_for_fit":False,"can_override_final_gate":False}
