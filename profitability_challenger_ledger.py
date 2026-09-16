#!/usr/bin/env python3
"""Durable prospective challenger ledger for ATLAS.

Freezes challenger definitions once and evaluates ONLY observations captured after
freeze. Research/paper-only: never mutates Production decisions.
"""
from __future__ import annotations
import json, math, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
RESEARCH=ROOT/'status/profitability-research-latest.json'
ATTR=ROOT/'status/analyst-forward-attribution-latest.json'
REGISTRY=ROOT/'status/profitability-challenger-registry.json'
OUT=ROOT/'status/profitability-prospective-shadow-latest.json'
MIN_N=10
COST_BPS=10.0
MAX_DD_R=3.0

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def tags(e):
    c=e.get('context') or {}
    d={'symbol':e.get('symbol'),'direction':e.get('direction'),'playbook':c.get('playbook'),'regime':c.get('regime'),
       'score_bucket':c.get('score_bucket'),'breakout_confirmed':c.get('breakout_confirmed'),'futures_reason':c.get('futures_reason'),
       'relative_strength_reason':c.get('relative_strength_reason'),'extension_guard_reason':c.get('extension_guard_reason'),
       'structural_geometry_source':c.get('structural_geometry_source')}
    return {k:str(v) for k,v in d.items() if v is not None}
def matches(e,f):
    t=tags(e); return all(t.get(k)==str(v) for k,v in f.items())
def metrics(vals):
    xs=[x for x in (num(v) for v in vals) if x is not None]; wins=[x for x in xs if x>0]; losses=[x for x in xs if x<0]
    eq=peak=dd=0.0
    for x in xs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    gp=sum(wins); gl=abs(sum(losses))
    return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4) if xs else None,'net_r':round(sum(xs),4) if xs else None,
            'positive_pct':round(100*len(wins)/len(xs),2) if xs else None,'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),
            'max_drawdown_r':round(dd,4) if xs else None}
def load_or_freeze():
    if REGISTRY.exists(): return json.loads(REGISTRY.read_text())
    r=json.loads(RESEARCH.read_text()); now=datetime.now(timezone.utc).isoformat()
    reg={'schema':'ATLAS_PROFITABILITY_CHALLENGER_REGISTRY_V1','frozen_at':now,'source_schema':r.get('schema'),
         'challengers':[{'challenger_id':x['challenger_id'],'frozen_filter':x['frozen_filter']} for x in r.get('challenger_registry') or []],
         'immutable_policy':'Never rewrite filters automatically; observations must be captured strictly after frozen_at.',
         'production_effect':'NONE'}
    REGISTRY.parent.mkdir(parents=True,exist_ok=True); REGISTRY.write_text(json.dumps(reg,indent=2,sort_keys=True)); return reg
def build():
    reg=load_or_freeze(); attr=json.loads(ATTR.read_text()); freeze=reg['frozen_at']; rows=[]
    for e in attr.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple')); ts=e.get('captured_at') or ''
        if ts>freeze and s.get('terminal') and r is not None: rows.append((e,r))
    challengers=[]
    for c in reg.get('challengers') or []:
        vals=[r for e,r in rows if matches(e,c['frozen_filter'])]; m=metrics(vals)
        # Cost conversion requires position risk/entry not consistently present in attribution; never fake it.
        cost_ready=False; net=m
        checks={'min_new_prospective_n':m['n']>=MIN_N,'gross_avg_r_positive':m['avg_r'] is not None and m['avg_r']>0,
                'gross_profit_factor_gt_1':m['profit_factor']=='INF' or (isinstance(m['profit_factor'],(int,float)) and m['profit_factor']>1),
                'max_drawdown_r_lte':m['max_drawdown_r'] is not None and m['max_drawdown_r']<=MAX_DD_R,
                'cost_adjusted_r_available':cost_ready}
        challengers.append({**c,'prospective_gross':m,'cost_basis_bps_target':COST_BPS,'cost_adjusted':None,
                            'checks':checks,'promotion_ready':all(checks.values()),'production_effect':'NONE'})
    return {'schema':'ATLAS_PROFITABILITY_PROSPECTIVE_SHADOW_V1','frozen_at':freeze,'new_terminal_market_observations':len(rows),
            'challengers':challengers,'promotion_policy':{'min_n':MIN_N,'target_cost_bps':COST_BPS,'max_drawdown_r':MAX_DD_R,
            'requires_cost_adjusted_positive_expectancy':True,'requires_profit_factor_gt_1':True,'automatic_promotion':False},
            'stage':'PROSPECTIVE_SHADOW','production_mutation_authorized':False,'research_only':True}
def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
