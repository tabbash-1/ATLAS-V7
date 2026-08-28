#!/usr/bin/env python3
"""Record-level, research-only replay of V6 WAIT outcomes.

Compares predeclared shadow ranking formulas with the V6 baseline on the same
independent V6 episodes and equal-coverage top-k cohorts. Never mutates Production.
"""
from __future__ import annotations
import json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC=Path('status/wait-outcomes.json')
OUT=Path('status/v6-shadow-replay.json')
GAP=timedelta(hours=12)
V6_PREFIX='PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE'
ALIASES={'VERY_CLOSE':'VERY_CLOSE_PRIOR_STRUCTURE','CLOSE':'CLOSE_PRIOR_STRUCTURE'}

def num(v, default=None):
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception:return default

def dt(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception:return None

def ctx(r): return r.get('decision_context') or {}
def attr(r): return r.get('score_attribution') or {}
def version(r): return str(ctx(r).get('scoring_version') or r.get('scoring_version') or '').upper()
def obstacle(r):
    x=str(attr(r).get('obstacle_reason') or 'NONE').upper()
    return ALIASES.get(x,x)
def rv(r): return num(ctx(r).get('relative_volume'), num(r.get('relative_volume'),0.0))
def rs_reason(r): return str(attr(r).get('relative_strength_reason') or 'NEUTRAL').upper()
def votes(r): return int(num(ctx(r).get('direction_votes'), num(r.get('direction_votes'),0)) or 0)
def baseline(r): return num(r.get('score'), num(attr(r).get('final_score'),0.0))
def future_adj(r): return num(attr(r).get('futures_adjustment'),0.0)
def obstacle_adj(r): return num(attr(r).get('obstacle_adjustment'),0.0)

def independent(rows):
    groups=defaultdict(list)
    for r in rows:
        if not version(r).startswith(V6_PREFIX): continue
        d=str(r.get('candidate_direction') or r.get('direction') or '').upper()
        t=dt(r.get('wait_at') or r.get('timestamp'))
        if d not in ('LONG','SHORT') or not t: continue
        key=(str(r.get('symbol') or '').upper(),d,obstacle(r),version(r))
        groups[key].append((t,r))
    out=[]
    for key,items in groups.items():
        last=None
        for t,r in sorted(items,key=lambda x:x[0]):
            if last is None or t-last>=GAP:
                x=dict(r); x['_episode_time']=t.isoformat(); out.append(x); last=t
    return out

def ret(r,h): return num((r.get('horizons') or {}).get(h,{}).get('directional_return_pct'))
def metrics(rows,h):
    vals=[ret(r,h) for r in rows]; vals=[v for v in vals if v is not None]
    if not vals:return {'n':0,'win_rate_pct':None,'mean_pct':None,'median_pct':None,'p10_pct':None,'loss_rate_le_minus_2pct':None}
    s=sorted(vals); p10=s[max(0,math.ceil(len(s)*.10)-1)]
    return {
      'n':len(vals),'win_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2),
      'mean_pct':round(statistics.mean(vals),4),'median_pct':round(statistics.median(vals),4),
      'p10_pct':round(p10,4),'loss_rate_le_minus_2pct':round(100*sum(v<=-2 for v in vals)/len(vals),2)
    }

def score_A(r):
    # Conservative attribution cleanup: remove unsupported vote premium, cap futures,
    # cap the severe very-close obstacle penalty, preserve proven RS and native RV bonus.
    s=baseline(r)
    if votes(r)>=4: s-=4
    f=future_adj(r); s += max(-1,min(1,f))-f
    oa=obstacle_adj(r)
    if oa < -4: s += (-4-oa)
    return s

def score_B(r):
    # A + explicit weak-volume quality penalties; no extra reward for RV>=1 because
    # V6 already rewards it through volume_bonus.
    s=score_A(r); v=rv(r)
    if v < .15:s-=6
    elif v < .30:s-=4
    elif v < .60:s+=0
    elif v < 1.0:s-=2
    return s

def score_C(r):
    # B + modest RS quality overlay, deliberately smaller than native +6.
    s=score_B(r)
    if rs_reason(r)=='ALIGNED_STRONG':s+=2
    return s

CANDIDATES={'BASELINE':baseline,'A_ATTRIBUTION_CLEANUP':score_A,'B_VOLUME_QUALITY':score_B,'C_VOLUME_PLUS_RS':score_C}

def equal_coverage(eps,h,k):
    out={}
    for name,fn in CANDIDATES.items():
        eligible=[r for r in eps if ret(r,h) is not None]
        ranked=sorted(eligible,key=lambda r:(fn(r),baseline(r)),reverse=True)[:k]
        out[name]={'metrics':metrics(ranked,h),'symbols':dict(sorted(__import__('collections').Counter(str(r.get('symbol') or '').upper() for r in ranked).items())),'score_floor':round(fn(ranked[-1]),3) if ranked else None}
    return out

def main():
    raw=json.loads(SRC.read_text()).get('records') or []
    eps=independent(raw)
    report={'schema':'ATLAS_V6_SHADOW_REPLAY_V1','generated_at':datetime.now(timezone.utc).isoformat(),'raw_records':len(raw),'independent_v6_episodes':len(eps),'episode_gap_hours':12,'candidate_definitions':{
      'A_ATTRIBUTION_CLEANUP':'remove +4 four-vote premium; cap futures to +/-1; cap obstacle penalty at -4',
      'B_VOLUME_QUALITY':'A plus penalties RV<0.15:-6, 0.15-0.29:-4, 0.60-0.99:-2',
      'C_VOLUME_PLUS_RS':'B plus +2 for ALIGNED_STRONG relative strength'},'comparisons':{},'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False}}
    for h in ('12h','24h'):
        n=sum(ret(r,h) is not None for r in eps)
        ks=sorted(set(k for k in (5,10,15,20,max(1,n//4),max(1,n//3)) if k<=n))
        report['comparisons'][h]={'available_n':n,'equal_coverage':{str(k):equal_coverage(eps,h,k) for k in ks}}
    # Select winner only if it beats baseline at both 12h and 24h for at least two
    # common cohort sizes on mean and win rate and does not worsen p10 materially.
    report['decision']={'status':'RESEARCH_ONLY_REVIEW_REQUIRED','rule':'No candidate is promoted automatically. Prefer consistency across horizons and cohort sizes over best single bucket.'}
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'episodes':len(eps),'12h':report['comparisons']['12h']['available_n'],'24h':report['comparisons']['24h']['available_n']}))
if __name__=='__main__':main()
