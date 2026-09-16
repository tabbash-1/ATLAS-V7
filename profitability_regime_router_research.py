#!/usr/bin/env python3
"""ATLAS native-regime router research V2.
Research only: classify native market regimes, measure path quality, and test an
expanding abstaining router without future leakage. Never changes Production.
"""
from __future__ import annotations
import json, math, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'status/analyst-forward-attribution-latest.json'
OUT=ROOT/'status/profitability-regime-router-latest.json'
MIN_PRIOR_LANE_N=4

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def ts(v):
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return datetime.min.replace(tzinfo=timezone.utc)

def metrics(rows):
    rs=[r['r'] for r in rows]; wins=[x for x in rs if x>0]; losses=[x for x in rs if x<0]; gp=sum(wins); gl=abs(sum(losses)); eq=peak=dd=0.0
    for x in rs: eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    def avg(k):
        a=[x[k] for x in rows if x[k] is not None]; return round(sum(a)/len(a),4) if a else None
    return {'n':len(rs),'avg_r':round(sum(rs)/len(rs),4) if rs else None,'net_r':round(sum(rs),4) if rs else None,
            'positive_pct':round(100*len(wins)/len(rs),2) if rs else None,'profit_factor':round(gp/gl,4) if gl else ('INF' if gp else None),
            'max_drawdown_r':round(dd,4) if rs else None,'avg_mfe_r':avg('mfe'),'avg_mae_r':avg('mae')}

def lane(e):
    c=e.get('context') or {}; reg=str(c.get('regime') or 'UNKNOWN').upper(); pb=str(c.get('playbook') or 'UNKNOWN').upper()
    if reg.startswith('BREAKOUT_'): return reg
    if reg in ('TREND_UP','TREND_DOWN'): return reg
    if 'RANGE' in reg: return 'RANGE'
    if 'REVERS' in reg: return 'REVERSAL'
    if 'PULLBACK' in pb: return 'PULLBACK_'+str(c.get('candidate_direction') or e.get('direction') or 'UNKNOWN').upper()
    return reg if reg!='UNKNOWN' else 'OTHER'

def build():
    src=json.loads(SRC.read_text()); rows=[]
    for e in src.get('entries') or []:
        s=e.get('settlement') or {}; r=num(s.get('r_multiple'))
        if not s.get('terminal') or r is None: continue
        rows.append({'captured_at':e.get('captured_at') or '', 'lane':lane(e),'r':r,'mfe':num(s.get('mfe_r')),'mae':num(s.get('mae_r'))})
    rows.sort(key=lambda x:ts(x['captured_at'])); cut=int(len(rows)*.625); disc=rows[:cut]; hold=rows[cut:]
    lanes={}
    for name in sorted(set(x['lane'] for x in rows)):
        dm=metrics([x for x in disc if x['lane']==name]); hm=metrics([x for x in hold if x['lane']==name])
        lanes[name]={'discovery':dm,'holdout':hm,'descriptive_only':True,
                     'path_quality_interpretation':'MFE/MAE diagnose path quality only; they do not authorize wider stops or farther targets.'}
    wf=[]
    for i in range(6,len(rows)):
        prior=[x for x in rows[:i] if x['lane']==rows[i]['lane']]; pm=metrics(prior); pf=pm['profit_factor']
        admit=(pm['n']>=MIN_PRIOR_LANE_N and pm['avg_r'] is not None and pm['avg_r']>0 and (pf=='INF' or (isinstance(pf,(int,float)) and pf>1)))
        wf.append({'captured_at':rows[i]['captured_at'],'lane':rows[i]['lane'],'prior_lane_n':pm['n'],'prior_lane_avg_r':pm['avg_r'],'prior_lane_profit_factor':pf,'router_would_admit':admit,'realized_r':rows[i]['r']})
    admitted=[x['realized_r'] for x in wf if x['router_would_admit']]; abstained=[x['realized_r'] for x in wf if not x['router_would_admit']]
    def sm(xs): return {'n':len(xs),'avg_r':round(sum(xs)/len(xs),4) if xs else None,'net_r':round(sum(xs),4) if xs else None}
    am=sm(admitted); promotion=(am['n']>=10 and am['avg_r'] is not None and am['avg_r']>0)
    return {'schema':'ATLAS_PROFITABILITY_NATIVE_REGIME_ROUTER_V2','horizon':'4-12H','chronological_discovery_n':len(disc),'chronological_holdout_n':len(hold),'lanes':lanes,
            'expanding_walk_forward':{'minimum_prior_lane_n':MIN_PRIOR_LANE_N,'observations':wf,'admitted':am,'abstained':sm(abstained),'policy':'Only earlier terminal outcomes from the same native regime are visible at each step.'},
            'router_candidate_ready':promotion,'decision':'RESEARCH_ONLY_NO_ROUTING_CHANGE','production_mutation_authorized':False,'automatic_promotion':False,'causal_claim':False,
            'notes':['Native TREND_UP and TREND_DOWN are kept separate; direction-specific regime behavior is not pooled.','Abstention is explicit when a lane lacks prior positive evidence.','Historical routing cannot authorize Production; prospective cost-aware validation remains mandatory.']}

def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
