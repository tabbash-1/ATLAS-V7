"""ATLAS early regime-transition predictor.

Predicts probability of directional expansion before a stable trend label exists.
All features are trailing/point-in-time. Future path is used only for labels.
Research-only challenger.
"""
from __future__ import annotations
import math,statistics
import historical_core_4_12h_replay as core
VERSION="ATLAS_TRANSITION_PREDICTOR_V1"
FEATURES=("er12","er24","atr_ratio","range_compression","vol_ratio","ret_accel","ema_slope_atr")

def _er(rows,n):
 if len(rows)<n+1:return 0.0
 c=[x["c"] for x in rows[-n-1:]]; path=sum(abs(c[i]-c[i-1]) for i in range(1,len(c)))
 return abs(c[-1]-c[0])/path if path else 0.0
def features(rows):
 a=core.atr(rows) or 1e-12;c=rows[-1]["c"];a_long=[]
 for i in range(max(15,len(rows)-60),len(rows)):
  q=core.atr(rows[:i+1])
  if q:a_long.append(q)
 am=statistics.mean(a_long) if a_long else a
 hi12=max(x["h"] for x in rows[-12:]);lo12=min(x["l"] for x in rows[-12:])
 hi48=max(x["h"] for x in rows[-48:]);lo48=min(x["l"] for x in rows[-48:])
 vols=[x["v"] for x in rows[-25:-1]];vm=statistics.mean(vols) if vols else rows[-1]["v"]
 r4=c/rows[-5]["c"]-1;r12=c/rows[-13]["c"]-1
 e0=core.ema([x["c"] for x in rows[-50:-4]],20);e1=core.ema([x["c"] for x in rows[-50:]],20)
 return {"er12":_er(rows,12),"er24":_er(rows,24),"atr_ratio":a/am if am else 1,
 "range_compression":(hi12-lo12)/(hi48-lo48) if hi48>lo48 else 1,
 "vol_ratio":rows[-1]["v"]/vm if vm else 1,"ret_accel":r4-r12/3,
 "ema_slope_atr":(e1-e0)/a if e0 is not None and e1 is not None else 0.0}

def label(entry,future,a,threshold=1.25):
 up=(max(x["h"] for x in future)-entry)/a;dn=(entry-min(x["l"] for x in future))/a
 if up>=threshold and up>dn*1.15:return "EXPAND_UP"
 if dn>=threshold and dn>up*1.15:return "EXPAND_DOWN"
 return "NO_EXPANSION"

def fit(samples):
 classes=("EXPAND_UP","EXPAND_DOWN","NO_EXPANSION");stats={};pri={}
 for y in classes:
  xs=[z for z in samples if z["y"]==y];pri[y]=max(len(xs),1)/max(len(samples),1);stats[y]={}
  for f in FEATURES:
   v=[float(z["x"][f]) for z in xs] or [0.0];stats[y][f]=(statistics.mean(v),max(statistics.pstdev(v),1e-6))
 return {"priors":pri,"stats":stats}
def predict(m,x):
 sc={}
 for y in m["priors"]:
  s=math.log(m["priors"][y])
  for f in FEATURES:
   mu,sd=m["stats"][y][f];z=(float(x[f])-mu)/sd;s+=-math.log(sd)-.5*z*z
  sc[y]=s
 mx=max(sc.values());ex={k:math.exp(v-mx) for k,v in sc.items()};den=sum(ex.values());p={k:ex[k]/den for k in ex}
 return {"probabilities":p,"prediction":max(p,key=p.get)}
def safety():return {"research_only":True,"production_impact":"NONE","future_features":False,"threshold":68,"can_override_final_gate":False}
