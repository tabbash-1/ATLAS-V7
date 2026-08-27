#!/usr/bin/env python3
"""ATLAS smart analysis of EXISTING wait outcomes.

Purpose: extract actionable research from data already collected before asking for
more samples. It never changes Production thresholds or scores. Results are kept
version-aware so old scoring logic cannot be mixed with the current engine and
misdiagnosed as a current calibration problem.
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

def version(r):
    return str((r.get('decision_context') or {}).get('scoring_version') or 'UNKNOWN').upper()
def obstacle(r):
    a=(r.get('score_attribution') or {}).get('obstacle_reason') or 'NONE'
    a=str(a).upper(); return ALIASES.get(a,a)
def attr(r,key,default=None):
    return (r.get('score_attribution') or {}).get(key,default)
def independent(rows):
    groups=defaultdict(list)
    for r in rows:
        d=str(r.get('candidate_direction') or '').upper(); t=dt(r.get('wait_at'))
        if d not in ('LONG','SHORT') or not t: continue
        key=(str(r.get('symbol') or '').upper(),d,obstacle(r),version(r))
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
    if v<1.00:return '0.60-0.99'
    return '>=1.00'
def bucket_numeric(v,step=2,label='x'):
    x=num(v)
    if x is None:return 'UNKNOWN'
    lo=math.floor(x/step)*step
    hi=lo+step
    return f'{label}:{lo:g}..{hi:g}'
def grouped_report(rows,keyfn):
    g=defaultdict(list)
    for r in rows:g[keyfn(r)].append(r)
    return {str(k):{'12h':stats(v,'12h'),'24h':stats(v,'24h')} for k,v in sorted(g.items(),key=lambda kv:str(kv[0]))}
def interaction(rows,*keyfns):
    return grouped_report(rows,lambda r:'|'.join(str(fn(r)) for fn in keyfns))
def attribution_report(rows):
    return {
      'by_trend_base': grouped_report(rows,lambda r:bucket_numeric(attr(r,'trend_base'),4,'trend')),
      'by_volume_bonus': grouped_report(rows,lambda r:bucket_numeric(attr(r,'volume_bonus'),2,'volbonus')),
      'by_relative_strength_adjustment': grouped_report(rows,lambda r:str(attr(r,'relative_strength_adjustment','UNKNOWN'))),
      'by_relative_strength_reason': grouped_report(rows,lambda r:str(attr(r,'relative_strength_reason','UNKNOWN'))),
      'by_futures_adjustment': grouped_report(rows,lambda r:bucket_numeric(attr(r,'futures_adjustment'),2,'fut')),
      'by_futures_reason': grouped_report(rows,lambda r:str(attr(r,'futures_reason','UNKNOWN'))),
      'by_obstacle_adjustment': grouped_report(rows,lambda r:str(attr(r,'obstacle_adjustment','UNKNOWN'))),
      'by_direction_votes': grouped_report(rows,lambda r:str((r.get('decision_context') or {}).get('direction_votes') or r.get('direction_votes') or 'UNKNOWN')),
      'score_x_volume_x_obstacle': interaction(rows,bucket_score,bucket_volume,obstacle),
      'direction_x_volume': interaction(rows,lambda r:str(r.get('candidate_direction') or 'NONE').upper(),bucket_volume),
    }
def main():
    payload=json.loads(SRC.read_text()); raw=payload.get('records') or []; eps=independent(raw)
    versions=sorted({version(r) for r in eps})
    version_reports={}
    for ver in versions:
        vr=[r for r in eps if version(r)==ver]
        version_reports[ver]={
            'episodes':len(vr),
            'overall':{'12h':stats(vr,'12h'),'24h':stats(vr,'24h')},
            'by_score_band':grouped_report(vr,bucket_score),
            'by_obstacle':grouped_report(vr,obstacle),
            'by_relative_volume':grouped_report(vr,bucket_volume),
            'score_x_obstacle':interaction(vr,bucket_score,obstacle),
            'score_x_volume':interaction(vr,bucket_score,bucket_volume),
            'direction_x_score':interaction(vr,lambda r:str(r.get('candidate_direction') or 'NONE').upper(),bucket_score),
            'attribution':attribution_report(vr),
        }
    current_versions=[v for v in versions if v.startswith('PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE')]
    current_rows=[r for r in eps if version(r) in current_versions]
    report={
      'schema':'ATLAS_SMART_EXISTING_RESULTS_V3_ATTRIBUTION_AWARE','generated_at':datetime.now(timezone.utc).isoformat(),
      'purpose':'Use existing independent evidence before requesting more data, without mixing scoring policies.',
      'raw_records':len(raw),'independent_directional_episodes':len(eps),'episode_gap_hours':12,
      'warning':'Cross-version pooled score bands are descriptive only. Production changes must be justified inside the matching scoring version.',
      'overall':{'12h':stats(eps,'12h'),'24h':stats(eps,'24h')},
      'by_scoring_version':version_reports,
      'current_v6_family':{
        'versions':current_versions,
        'episodes':len(current_rows),
        'overall':{'12h':stats(current_rows,'12h'),'24h':stats(current_rows,'24h')},
        'by_score_band':grouped_report(current_rows,bucket_score),
        'by_volume':grouped_report(current_rows,bucket_volume),
        'by_obstacle':grouped_report(current_rows,obstacle),
        'attribution':attribution_report(current_rows),
      },
      'by_symbol':grouped_report(eps,lambda r:str(r.get('symbol') or 'UNKNOWN').upper()),
      'by_direction':grouped_report(eps,lambda r:str(r.get('candidate_direction') or 'NONE').upper()),
      'by_score_band_descriptive_only':grouped_report(eps,bucket_score),
      'by_obstacle':grouped_report(eps,obstacle),
      'by_regime':grouped_report(eps,lambda r:str((r.get('decision_context') or {}).get('regime') or 'UNKNOWN')),
      'by_relative_volume':grouped_report(eps,bucket_volume),
      'by_playbook':grouped_report(eps,lambda r:str(r.get('playbook') or 'NONE')),
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_adjustment':0,'auto_promotion_enabled':False},
      'next_decision':'Use current_v6_family attribution to identify which score component is anti-predictive. Build a shadow candidate formula and compare it to V6 baseline before any Production change.'
    }
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'raw':len(raw),'episodes':len(eps),'versions':{v:version_reports[v]['episodes'] for v in versions},'current_v6_family_episodes':len(current_rows)},sort_keys=True))
if __name__=='__main__':main()
