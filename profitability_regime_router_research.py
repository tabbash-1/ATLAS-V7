#!/usr/bin/env python3
"""ATLAS regime-router and MFE/MAE path-quality research.

Research only. Uses chronological forward outcomes to test whether separate regime
lanes are more stable than a single global strategy. Never changes Production.
"""
from __future__ import annotations
import json, math, pathlib
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'status/analyst-forward-attribution-latest.json'
OUT=ROOT/'status/profitability-regime-router-latest.json'
MIN_DISCOVERY_N=3
MIN_HOLDOUT_N=2

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def metrics(rows):
    rs=[r['r'] for r in rows]; wins=[x for x in rs if x>0]; losses=[x for x in rs if x<0]
    gp=sum(wins); gl=abs(sum(losses)); eq=peak=dd=0.0
    for x in rs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    return {'n':len(rs),'avg_r':round(sum(rs)/len(rs),4) if rs else None,'net_r':round(sum(rs),4) if rs else None,
            'positive_pct':round(100*len(wins)/len(rs),2) if rs else None,
            'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),
            'max_drawdown_r':round(dd,4) if rs else None,
            'avg_mfe_r':round(sum(x['mfe'] for x in rows if x['mfe'] is not None)/sum(x['mfe'] is not None for x in rows),4) if any(x['mfe'] is not None for x in rows) else None,
            'avg_mae_r':round(sum(x['mae'] for x in rows if x['mae'] is not None)/sum(x['mae'] is not None for x in rows),4) if any(x['mae'] is not None for x in rows) else None}

def lane(e):
    c=e.get('context') or {}; reg=str(c.get('regime') or 'UNKNOWN'); pb=str(c.get('playbook') or 'UNKNOWN')
    if c.get('breakout_confirmed') is True or reg.startswith('BREAKOUT') or 'BREAKOUT_CONFIRMED' in pb: return 'CONFIRMED_BREAKOUT'
    if 'PULLBACK' in pb: return 'PULLBACK'
    if reg in ('TREND_UP','TREND_DOWN') or 'CONTINUATION' in pb: return 'TREND_CONTINUATION'
    if 'RANGE' in reg or 'REVERS' in pb: return 'RANGE_REVERSAL'
    return 'OTHER'

def build():
    src=json.loads(SRC.read_text()); rows=[]
    for e in src.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple'))
        if not s.get('terminal') or r is None: continue
        rows.append({'captured_at':e.get('captured_at') or '', 'lane':lane(e),'r':r,'mfe':num(s.get('mfe_r')),'mae':num(s.get('mae_r'))})
    rows.sort(key=lambda x:x['captured_at']); cut=int(len(rows)*.625); disc=rows[:cut]; hold=rows[cut:]
    lanes={}
    for name in sorted(set(x['lane'] for x in rows)):
        d=[x for x in disc if x['lane']==name]; h=[x for x in hold if x['lane']==name]
        dm,hm=metrics(d),metrics(h)
        pf=hm['profit_factor']; stable=(dm['n']>=MIN_DISCOVERY_N and hm['n']>=MIN_HOLDOUT_N and dm['avg_r'] is not None and dm['avg_r']>0 and hm['avg_r'] is not None and hm['avg_r']>0 and (pf=='INF' or (isinstance(pf,(int,float)) and pf>1)))
        lanes[name]={'discovery':dm,'holdout':hm,'holdout_positive_stability':stable,
                     'path_quality_interpretation':'MFE/MAE are descriptive path evidence, not an instruction to widen stops or chase targets.'}
    # Expanding chronological walk-forward: each point is evaluated only after a minimum prior history.
    wf=[]
    for i in range(6,len(rows)):
        train=rows[:i]; test=rows[i]; lm=metrics([x for x in train if x['lane']==test['lane']])
        eligible=lm['n']>=MIN_DISCOVERY_N and lm['avg_r'] is not None and lm['avg_r']>0
        wf.append({'captured_at':test['captured_at'],'lane':test['lane'],'prior_lane_n':lm['n'],'prior_lane_avg_r':lm['avg_r'],'router_would_admit':eligible,'realized_r':test['r']})
    admitted=[x['realized_r'] for x in wf if x['router_would_admit']]; rejected=[x['realized_r'] for x in wf if not x['router_would_admit']]
    def simple(xs): return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4) if xs else None,'net_r':round(sum(xs),4) if xs else None}
    return {'schema':'ATLAS_PROFITABILITY_REGIME_ROUTER_RESEARCH_V1','horizon':'4-12H','chronological_discovery_n':len(disc),'chronological_holdout_n':len(hold),
            'lanes':lanes,'expanding_walk_forward':{'observations':wf,'admitted':simple(admitted),'rejected':simple(rejected),
            'policy':'At each step use only earlier outcomes from the same regime lane; no future leakage.'},
            'decision':'RESEARCH_ONLY_NO_ROUTING_CHANGE','production_mutation_authorized':False,'automatic_promotion':False,'causal_claim':False,
            'notes':['Small samples remain exploratory.','No lane may alter canonical LONG/SHORT/WAIT until prospective cost-aware evidence passes.']}

def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__': main()
