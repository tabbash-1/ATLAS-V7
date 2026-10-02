"""ATLAS Trade Outcome Predictor V1.

Predicts P(TP-before-SL) for a proposed UP/DOWN trade from point-in-time features.
Labels inspect future candles only after features/candidate side are frozen.
Research-only; no Production authority.
"""
from __future__ import annotations
import math,statistics
import profitability_prediction_engine as pe
VERSION="ATLAS_TRADE_OUTCOME_PREDICTOR_V1"
FEATURES=pe.FEATURES+("side_up","direction_confidence")

def vector(x,side,confidence):
 q={f:float(x[f]) for f in pe.FEATURES};q["side_up"]=1.0 if side=="UP" else 0.0;q["direction_confidence"]=float(confidence);return q
def outcome(entry,a,side,future,reward_r=2.0,risk_r=1.0):
 risk=1.5*a; stop=entry-risk if side=="UP" else entry+risk;tp=entry+reward_r*risk if side=="UP" else entry-reward_r*risk
 for c in future[:12]:
  hs=c["l"]<=stop if side=="UP" else c["h"]>=stop
  ht=c["h"]>=tp if side=="UP" else c["l"]<=tp
  if hs and ht:return 0
  if hs:return 0
  if ht:return 1
 return None
def fit(samples):
 pos=[z for z in samples if z["y"]==1];neg=[z for z in samples if z["y"]==0];n=max(len(samples),1)
 m={"prior":max(len(pos),1)/n,"stats":{}}
 for y,rows in ((1,pos),(0,neg)):
  m["stats"][y]={}
  for f in FEATURES:
   v=[z["x"][f] for z in rows] or [0.0];m["stats"][y][f]=(statistics.mean(v),max(statistics.pstdev(v),1e-6))
 return m
def predict(m,x):
 scores={}
 for y in (1,0):
  prior=m["prior"] if y==1 else 1-m["prior"];s=math.log(max(prior,1e-9))
  for f in FEATURES:
   mu,sd=m["stats"][y][f];z=(x[f]-mu)/sd;s+=-math.log(sd)-.5*z*z
  scores[y]=s
 mx=max(scores.values());a=math.exp(scores[1]-mx);b=math.exp(scores[0]-mx);p=a/(a+b)
 return {"p_tp_before_sl":p,"p_sl_before_tp":1-p,"expected_r":p*2-(1-p)*1}
def safety():return {"research_only":True,"production_impact":"NONE","threshold":68,"future_features":False,"reward_r":2.0,"risk_r":1.0}
