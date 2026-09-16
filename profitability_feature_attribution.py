#!/usr/bin/env python3
"""Numeric feature attribution for ATLAS forward outcomes; research only."""
from __future__ import annotations
import json, math, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'status/analyst-forward-attribution-latest.json'
OUT=ROOT/'status/profitability-feature-attribution-latest.json'
FEATURES=['score','rsi','atr','momentum','paced_relative_volume','relative_strength_adjustment','futures_adjustment','obstacle_adjustment','extension_adjustment','body_atr']

def n(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except Exception:return None
def value(e,k):
 c=e.get('context') or {}; a=c.get('score_attribution') or {}
 aliases={'score':['score'],'rsi':['rsi'],'atr':['atr'],'momentum':['momentum'],'paced_relative_volume':['paced_relative_volume','relative_volume','paced_rv'],'relative_strength_adjustment':['relative_strength_adjustment','rs_adjustment'],'futures_adjustment':['futures_adjustment'],'obstacle_adjustment':['obstacle_adjustment','prior_structure_obstacle_adjustment'],'extension_adjustment':['extension_adjustment'],'body_atr':['body_atr','body_atr_ratio']}
 for key in aliases[k]:
  for d in (c,a,e):
   x=n(d.get(key)) if isinstance(d,dict) else None
   if x is not None:return x
 return None
def metrics(xs):
 if not xs:return {'n':0,'avg_r':None,'net_r':None,'positive_pct':None}
 return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4),'net_r':round(sum(xs),4),'positive_pct':round(100*sum(x>0 for x in xs)/len(xs),2)}
def build():
 src=json.loads(SRC.read_text()); rows=[]
 for e in src.get('entries') or []:
  s=e.get('settlement') or {}; r=n(s.get('r_multiple'))
  if s.get('terminal') and r is not None: rows.append((e,r))
 rows.sort(key=lambda z:z[0].get('captured_at') or ''); cut=int(len(rows)*.625); disc=rows[:cut]; hold=rows[cut:]
 out={}
 for f in FEATURES:
  vals=[value(e,f) for e,_ in disc]; clean=sorted(x for x in vals if x is not None)
  if len(clean)<4: out[f]={'status':'INSUFFICIENT_FEATURE_COVERAGE','available_n':len(clean)}; continue
  median=clean[len(clean)//2]
  def side(data,hi): return [r for e,r in data if value(e,f) is not None and ((value(e,f)>=median) if hi else (value(e,f)<median))]
  out[f]={'status':'DESCRIPTIVE_NOT_CAUSAL','predeclared_split':'discovery_median','split_value':median,
          'discovery':{'low':metrics(side(disc,False)),'high':metrics(side(disc,True))},
          'holdout':{'low':metrics(side(hold,False)),'high':metrics(side(hold,True))}}
 return {'schema':'ATLAS_PROFITABILITY_FEATURE_ATTRIBUTION_V1','horizon':'4-12H','chronological_discovery_n':len(disc),'chronological_holdout_n':len(hold),'features':out,
         'interpretation':'Descriptive forward attribution only. No threshold fishing, no causal claims, no Production mutation.',
         'production_mutation_authorized':False,'automatic_promotion':False,'research_only':True}
def main():
 x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
