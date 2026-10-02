"""Locked research metrics/cost model for true-path outcome evaluation."""
import math
VERSION="ATLAS_TRUE_PATH_METHODOLOGY_V2"
FEE_BPS_PER_SIDE=10.0
SLIPPAGE_BPS_PER_SIDE=5.0
ROUND_TRIP_COST_BPS=2*(FEE_BPS_PER_SIDE+SLIPPAGE_BPS_PER_SIDE)
PURGE_HOURS=12
EMBARGO_HOURS=12

def cost_r(entry,atr):
 risk=1.5*float(atr)
 return (float(entry)*(ROUND_TRIP_COST_BPS/10000.0))/risk if risk>0 else 0.0

def net_r(y,entry,atr):
 gross=2.0 if int(y)==1 else -1.0
 return gross-cost_r(entry,atr)

def probability_metrics(rows):
 if not rows:return {"n":0,"brier":None,"log_loss":None}
 eps=1e-12;b=0.0;ll=0.0
 for z in rows:
  p=min(1-eps,max(eps,float(z["p"])));y=int(z["y"])
  b+=(p-y)**2;ll+=-(y*math.log(p)+(1-y)*math.log(1-p))
 n=len(rows);return {"n":n,"brier":round(b/n,6),"log_loss":round(ll/n,6)}

def safety():return {"research_only":True,"production_impact":"NONE","threshold":68,"fees_bps_per_side":FEE_BPS_PER_SIDE,"slippage_bps_per_side":SLIPPAGE_BPS_PER_SIDE,"round_trip_cost_bps":ROUND_TRIP_COST_BPS,"purge_hours":PURGE_HOURS,"embargo_hours":EMBARGO_HOURS,"can_override_final_gate":False}
