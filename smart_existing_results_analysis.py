#!/usr/bin/env python3
"""ATLAS smart analysis of EXISTING wait outcomes.

Purpose: extract actionable research from data already collected before asking for
more samples. It never changes Production thresholds or scores.
"""
from __future__ import annotations
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC=Path('status/wait-outcomes.json')
OUT=Path('status/smart-existing-results-analysis.json')
GAP=timedelta(hours=12)
ALIASES={'VERY_CLOSE':'VERY_CLOSE_PRIOR_STRUCTURE','CLOSE':'CLOSE_PRIOR_STRUCTURE'}


def dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except:return None

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except:return None

def obstacle(r):
    a=(r.get('score_attribution') or {}).get('obstacle_reason') or 'NONE'
    a=str(a).upper(); return ALIASES.get(a,a)

def independent(rows):
    groups=defaultdict(list)
    for r in rows:
        d=str(r.get('candidate_direction') or '').upper(); t=dt(r.get('wait_at'))
        if d not in ('LONG','SHORT') or not t: continue
        key=(str(r.get('symbol') or '').upper(),d,obstacle(r))
        groups[key].append((t,r))
    out=[]
    for key,items in groups.items():
        last=None
        for t,r in sorted(items):
            if last is None or t-last>=GAP:
                x=dict(r); x['_combo']='|'.join(key); out.append(x); last=t
    return out

def stats(rows,h='12h'):
    vals=[num((r.get('horizons') or {}).get(h,{}).get('directional_return_pct')) for r in rows]
    vals=[v for v in vals if v is not None]
    if not vals:return {'n':0,'win_rate_pct':None,'mean_pct':None,'median_pct':None}
    return {'n':len(vals),'win_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2),'mean_pct':round(statistics.mean(vals),4),'median_pct':round(statistics.median(vals),4)}

def bucket_score(r):
    s=num(r.get('score'))
    if s is None:return 'NO_SCORE'
    lo=int(s//4)*4
    return f'{lo}-{lo+3}'

def bucket_volume(r):
    v=num((r.get('decision_context') or {}).get('relative_volume'))
    if v is None:return 'UNKNOWN'
    if v<0.15:return '<0.15'
    if v<0.30:return '0.15-0.29'
    if v<0.60:return '0.30-0.59'
    return '>=0.60'

def grouped_report(rows,keyfn):
    g=defaultdict(list)
    for r in rows:g[keyfn(r)].append(r)
    return {k:{'12h':stats(v,'12h'),'24h':stats(v,'24h')} for k,v in sorted(g.items())}

def main():
    payload=json.loads(SRC.read_text()); raw=payload.get('records') or []; eps=independent(raw)
    report={
      'schema':'ATLAS_SMART_EXISTING_RESULTS_V1','generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'Use existing independent evidence before requesting more data.',
      'raw_records':len(raw),'independent_directional_episodes':len(eps),'episode_gap_hours':12,
      'overall':{'12h':stats(eps,'12h'),'24h':stats(eps,'24h')},
      'by_symbol':grouped_report(eps,lambda r:str(r.get('symbol') or 'UNKNOWN').upper()),
      'by_direction':grouped_report(eps,lambda r:str(r.get('candidate_direction') or 'NONE').upper()),
      'by_score_band':grouped_report(eps,bucket_score),
      'by_obstacle':grouped_report(eps,obstacle),
      'by_regime':grouped_report(eps,lambda r:str((r.get('decision_context') or {}).get('regime') or 'UNKNOWN')),
      'by_relative_volume':grouped_report(eps,bucket_volume),
      'by_playbook':grouped_report(eps,lambda r:str(r.get('playbook') or 'NONE')),
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_adjustment':0,'auto_promotion_enabled':False},
      'next_decision':'Compare segments on existing independent episodes; only propose a Production change if it improves out-of-sample/regression evidence versus baseline.'
    }
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'raw':len(raw),'episodes':len(eps),'overall_12h':report['overall']['12h']},sort_keys=True))
if __name__=='__main__':main()
