#!/usr/bin/env python3
"""Predeclared ATLAS edge-intersection research lane.

Tests the current strongest non-causal hypothesis without threshold fishing:
strong relative strength + high score + acceptable structural obstacle.
Thresholds are frozen from discovery medians already emitted by feature attribution.
Research/shadow only; cannot mutate Production.
"""
from __future__ import annotations
import json, math, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
ATTR=ROOT/'status/analyst-forward-attribution-latest.json'
FEAT=ROOT/'status/profitability-feature-attribution-latest.json'
OUT=ROOT/'status/profitability-edge-intersection-shadow-latest.json'
MIN_PROSPECTIVE_N=10

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def getv(e,key):
    c=e.get('context') or {}; a=c.get('score_attribution') or {}
    aliases={'score':['score'],'relative_strength_adjustment':['relative_strength_adjustment','rs_adjustment'],
             'obstacle_adjustment':['obstacle_adjustment','prior_structure_obstacle_adjustment']}
    for k in aliases[key]:
        for d in (c,a,e):
            if isinstance(d,dict):
                x=num(d.get(k))
                if x is not None:return x
    return None

def met(rs):
    if not rs:return {'n':0,'avg_r':None,'net_r':None,'positive_pct':None,'profit_factor':None,'max_drawdown_r':None}
    w=[x for x in rs if x>0]; l=[x for x in rs if x<0]; gp=sum(w); gl=abs(sum(l)); eq=peak=dd=0.0
    for x in rs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    return {'n':len(rs),'avg_r':round(sum(rs)/len(rs),4),'net_r':round(sum(rs),4),'positive_pct':round(100*len(w)/len(rs),2),
            'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),'max_drawdown_r':round(dd,4)}

def build():
    f=json.loads(FEAT.read_text()); a=json.loads(ATTR.read_text())
    th={k:num(f['features'][k]['split_value']) for k in ('score','relative_strength_adjustment','obstacle_adjustment')}
    if any(v is None for v in th.values()): raise RuntimeError('required frozen discovery split unavailable')
    rows=[]
    for e in a.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple'))
        if not s.get('terminal') or r is None: continue
        vals={k:getv(e,k) for k in th}; admit=all(vals[k] is not None and vals[k]>=th[k] for k in th)
        rows.append({'captured_at':e.get('captured_at') or '', 'r':r,'admit':admit,'values':vals})
    rows.sort(key=lambda x:x['captured_at']); cut=int(len(rows)*.625); d=rows[:cut]; h=rows[cut:]
    dm=met([x['r'] for x in d if x['admit']]); hm=met([x['r'] for x in h if x['admit']])
    # This lane is a new frozen hypothesis from this report forward; historical holdout is validation evidence, never prospective evidence.
    return {'schema':'ATLAS_EDGE_INTERSECTION_SHADOW_V1','hypothesis_id':'RS_SCORE_STRUCTURE_V1','horizon':'4-12H',
            'frozen_thresholds':th,'rule':'score>=split AND relative_strength_adjustment>=split AND obstacle_adjustment>=split',
            'discovery':dm,'historical_holdout':hm,'prospective_new_n':0,'minimum_prospective_n':MIN_PROSPECTIVE_N,
            'prospective_cost_adjusted_required':True,'promotion_ready':False,'automatic_promotion':False,
            'production_mutation_authorized':False,'decision':'FREEZE_AND_COLLECT_PROSPECTIVE_EVIDENCE',
            'warnings':['Thresholds come only from prior discovery medians.','Historical holdout is not counted as new prospective evidence.','No Production routing change is authorized.']}

def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
