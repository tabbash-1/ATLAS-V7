#!/usr/bin/env python3
"""Offline evaluation of committed ATLAS Production snapshots.

Research-only. Reads historical snapshots, computes later directional returns,
and writes a report. It cannot modify Production or execution state.
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, statistics
from pathlib import Path

SCHEMA='ATLAS_OFFLINE_FORWARD_EVALUATION_V1'
HORIZONS=(1,3,6,12,24)


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
            last[key]=t0
            x={'symbol':symbol,'captured_at':t0.isoformat(),'classification':klass,'direction':side,'score':f(d0.get('score')),'wait_reason':d0.get('wait_reason'),'horizons':{}}
            for h in HORIZONS:
                hit=nearest(rows,i,symbol,t0+dt.timedelta(hours=h))
                if not hit:continue
                t1,p1=hit; market=(p1/p0-1)*100; dr=market if side=='LONG' else -market
                x['horizons'][str(h)]={'observed_at':t1.isoformat(),'directional_return_pct':round(dr,6)}
            obs.append(x)
    def agg(items):
        return {str(h):metrics([((x.get('horizons') or {}).get(str(h)) or {}).get('directional_return_pct') for x in items]) for h in HORIZONS}
    now=dt.datetime.now(dt.timezone.utc); latest=rows[-1][0] if rows else None
    age=((now-latest).total_seconds()/60) if latest else None
    q=[x for x in obs if x['classification']=='QUALIFIED']; w=[x for x in obs if x['classification']=='WAIT_DIRECTIONAL']
    return {'schema':SCHEMA,'generated_at':now.isoformat(),'research_only':True,'live_execution':False,'can_override_production':False,'production_threshold_changed':False,'source':{'file':'status/history/production-snapshots.jsonl','snapshot_rows':len(rows),'latest_snapshot_at':latest.isoformat() if latest else None,'latest_snapshot_age_minutes':round(age,2) if age is not None else None,'stale':age is None or age>90},'sampling':'max one row per symbol/class/direction per hour','overall':agg(obs),'qualified':agg(q),'wait_directional':agg(w),'observation_count':len(obs),'latest_observations':obs[-80:]}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--history',default='status/history/production-snapshots.jsonl'); ap.add_argument('--output',default='status/offline-forward-evaluation-latest.json'); a=ap.parse_args()
    report=build(load(Path(a.history))); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({'schema':report['schema'],'snapshots':report['source']['snapshot_rows'],'observations':report['observation_count'],'12h':report['overall']['12']},sort_keys=True))

if __name__=='__main__':main()
