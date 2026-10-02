"""Locked research methodology for true-path profitability evidence V2."""
from __future__ import annotations
import math
VERSION="ATLAS_TRUE_PATH_EVIDENCE_V2"
PURGE_HOURS=12
EMBARGO_HOURS=12
FEE_R=0.02
SLIPPAGE_R=0.02
TOTAL_COST_R=FEE_R+SLIPPAGE_R

def net_r(y,reward_r=2.0,risk_r=1.0):
    if y==1:return reward_r-TOTAL_COST_R
    if y==0:return -risk_r-TOTAL_COST_R
    return 0.0

def metrics(probs,ys):
    pairs=[(float(p),int(y)) for p,y in zip(probs,ys) if y in (0,1)]
    if not pairs:return {"n":0,"brier":None,"log_loss":None}
    b=sum((p-y)**2 for p,y in pairs)/len(pairs)
    ll=-sum(y*math.log(max(min(p,1-1e-12),1e-12))+(1-y)*math.log(max(min(1-p,1-1e-12),1e-12)) for p,y in pairs)/len(pairs)
    return {"n":len(pairs),"brier":b,"log_loss":ll}

def temporal_split(rows,train_frac=.60,validation_frac=.20):
    rows=sorted(rows,key=lambda z:z["t"])
    if not rows:return {"train":[],"validation":[],"test":[]}
    a=rows[max(0,int(len(rows)*train_frac)-1)]["t"];b=rows[max(0,int(len(rows)*(train_frac+validation_frac))-1)]["t"]
    hour=3600000
    gap=(PURGE_HOURS+EMBARGO_HOURS)*hour
    # Count-based cut points can be closer than the locked temporal exclusion
    # window (for example, 100 hourly rows with a 20% validation fold). Expand
    # the two boundaries symmetrically so a valid validation observation can
    # exist without weakening either the purge or embargo contract.
    if b-a<gap:
        shortfall=gap-(b-a)
        left=shortfall//2
        a-=left
        b+=shortfall-left
    min_a=rows[0]["t"]+PURGE_HOURS*hour
    max_b=rows[-1]["t"]-EMBARGO_HOURS*hour
    if a<min_a:
        shift=min_a-a;a+=shift;b+=shift
    if b>max_b:
        shift=b-max_b;a-=shift;b-=shift
    return {"train":[z for z in rows if z["t"]<=a-PURGE_HOURS*3600000],
      "validation":[z for z in rows if z["t"]>=a+EMBARGO_HOURS*3600000 and z["t"]<=b-PURGE_HOURS*3600000],
      "test":[z for z in rows if z["t"]>=b+EMBARGO_HOURS*3600000],
      "train_boundary":a,"validation_boundary":b,"boundary_gap_ms":gap}

def safety():return {"research_only":True,"production_impact":"NONE","threshold":68,"purge_hours":PURGE_HOURS,"embargo_hours":EMBARGO_HOURS,"fee_r":FEE_R,"slippage_r":SLIPPAGE_R,"costs_locked":True,"can_override_final_gate":False}
