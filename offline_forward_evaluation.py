#!/usr/bin/env python3
"""Offline evaluation of committed ATLAS Production snapshots.
Research-only; cannot modify Production or execution state.
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, statistics
from collections import Counter
from pathlib import Path

SCHEMA='ATLAS_OFFLINE_FORWARD_EVALUATION_V3_ROBUSTNESS'
HORIZONS=(1,3,4,6,12,24)


def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def ts(v):
    try:return dt.datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except Exception:return None

def price(d):
    for k in ('entry','price','current_price','market_price','last_price','close'):
        x=f((d or {}).get(k))
        if x and x>0:return x
    return None

def direction(d):
    for k in ('candidate_direction','direction','decision'):
        v=str((d or {}).get(k) or '').upper()
        if v in ('LONG','SHORT'):return v
    return None

def score_band(v):
    x=f(v)
    if x is None:return 'UNKNOWN'
    if x<50:return 'LT50'
    if x<60:return '50_59'
    if x<68:return '60_67'
    if x<75:return '68_74'
    if x<82:return '75_81'
    return '82_PLUS'

def metrics(vals):
    a=[float(x) for x in vals if x is not None]
    if not a:return {'n':0,'mean_pct':None,'median_pct':None,'positive_rate_pct':None}
    return {'n':len(a),'mean_pct':round(sum(a)/len(a),6),'median_pct':round(statistics.median(a),6),'positive_rate_pct':round(100*sum(x>0 for x in a)/len(a),4)}
def load(path):
    out=[]
    if not path.exists():return out
    for line in path.read_text(errors='replace').splitlines():
        try:r=json.loads(line)
        except Exception:continue
        t=ts(r.get('captured_at'))
        if t:out.append((t,r))
    return sorted(out,key=lambda x:x[0])
def nearest(rows,i,symbol,target):
    limit=target+dt.timedelta(minutes=50)
    for t,r in rows[i+1:]:
        if t<target:continue
        if t>limit:return None
        p=price(((r.get('decisions') or {}).get(symbol) or {}))
        if p:return t,p
    return None
def aggregate(items):
    return {str(h):metrics([((x.get('horizons') or {}).get(str(h)) or {}).get('directional_return_pct') for x in items]) for h in HORIZONS}
def grouped(obs,keyfn):
    keys=sorted({str(keyfn(x)) for x in obs})
    return {k:aggregate([x for x in obs if str(keyfn(x))==k]) for k in keys}
def chronological_folds(items,n=3):
    a=sorted(items,key=lambda x:x['captured_at']); out=[]
    for i in range(n):
        fold=a[(i*len(a))//n:((i+1)*len(a))//n]
        out.append({'fold':i+1,'start_at':fold[0]['captured_at'] if fold else None,'end_at':fold[-1]['captured_at'] if fold else None,'all':aggregate(fold),'by_direction':grouped(fold,lambda x:x['direction'])})
    return out

def build(rows):
    obs=[]; last={}
    for i,(t0,r0) in enumerate(rows):
        for symbol,d0 in (r0.get('decisions') or {}).items():
            if not isinstance(d0,dict) or not d0.get('ok'):continue
            p0=price(d0); side=direction(d0)
            if not p0 or side not in ('LONG','SHORT'):continue
            klass='QUALIFIED' if d0.get('signal_qualified') else 'WAIT_DIRECTIONAL'
            key=(symbol,klass,side)
            if key in last and (t0-last[key]).total_seconds()<3600:continue
            last[key]=t0; score=f(d0.get('score'))
            x={'symbol':symbol,'captured_at':t0.isoformat(),'classification':klass,'direction':side,'score':score,'score_band':score_band(score),'wait_reason':d0.get('wait_reason'),'execution_ready':bool(d0.get('execution_ready')),'playbook':str(d0.get('playbook') or 'UNKNOWN'),'regime':str(d0.get('regime') or 'UNKNOWN'),'horizons':{}}
            for h in HORIZONS:
                hit=nearest(rows,i,symbol,t0+dt.timedelta(hours=h))
                if not hit:continue
                t1,p1=hit; market=(p1/p0-1)*100; dr=market if side=='LONG' else -market
                x['horizons'][str(h)]={'observed_at':t1.isoformat(),'directional_return_pct':round(dr,6)}
            obs.append(x)
    now=dt.datetime.now(dt.timezone.utc); latest=rows[-1][0] if rows else None; age=((now-latest).total_seconds()/60) if latest else None
    q=[x for x in obs if x['classification']=='QUALIFIED']; w=[x for x in obs if x['classification']=='WAIT_DIRECTIONAL']; q_exec=[x for x in q if x['execution_ready']]
    return {'schema':SCHEMA,'generated_at':now.isoformat(),'research_only':True,'live_execution':False,'can_override_production':False,'production_threshold_changed':False,'source':{'file':'status/history/production-snapshots.jsonl','snapshot_rows':len(rows),'latest_snapshot_at':latest.isoformat() if latest else None,'latest_snapshot_age_minutes':round(age,2) if age is not None else None,'stale':age is None or age>90},'sampling':'max one row per symbol/class/direction per hour','overall':aggregate(obs),'qualified':aggregate(q),'wait_directional':aggregate(w),'qualified_execution_ready':aggregate(q_exec),'qualified_by_symbol':grouped(q,lambda x:x['symbol']),'qualified_by_direction':grouped(q,lambda x:x['direction']),'qualified_by_score_band':grouped(q,lambda x:x['score_band']),'qualified_by_regime':grouped(q,lambda x:x['regime']),'qualified_by_playbook':grouped(q,lambda x:x['playbook']),'qualified_chronological_folds':chronological_folds(q,3),'wait_reason_counts':dict(Counter(str(x.get('wait_reason') or 'UNSPECIFIED') for x in w).most_common()),'observation_count':len(obs),'qualified_count':len(q),'wait_directional_count':len(w),'latest_observations':obs[-80:]}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--history',default='status/history/production-snapshots.jsonl'); ap.add_argument('--output',default='status/offline-forward-evaluation-latest.json'); a=ap.parse_args(); report=build(load(Path(a.history))); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({'schema':report['schema'],'qualified':report['qualified_count'],'4h':report['qualified']['4'],'12h':report['qualified']['12'],'folds':report['qualified_chronological_folds']},sort_keys=True))
if __name__=='__main__':main()
