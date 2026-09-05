#!/usr/bin/env python3
"""ATLAS unified monthly product audit.

Consumes committed Production snapshots only. This is an analyst-quality/evidence
report: it cannot change Production scoring, thresholds, decisions, or execution.
"""
from __future__ import annotations
import argparse, datetime as dt, json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = 'ATLAS_MONTHLY_PRODUCT_AUDIT_V1'
HORIZONS = (4, 8, 12)


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

def side(d):
    for k in ('candidate_direction','direction','decision'):
        v=str((d or {}).get(k) or '').upper()
        if v in ('LONG','SHORT'):return v
    return None

def load(path):
    rows=[]
    for line in path.read_text(errors='replace').splitlines() if path.exists() else []:
        try:r=json.loads(line)
        except Exception:continue
        t=ts(r.get('captured_at'))
        if t:rows.append((t,r))
    return sorted(rows,key=lambda x:x[0])

def nearest(rows,i,symbol,target):
    limit=target+dt.timedelta(minutes=55)
    for t,r in rows[i+1:]:
        if t<target:continue
        if t>limit:return None
        p=price(((r.get('decisions') or {}).get(symbol) or {}))
        if p:return t,p
    return None

def metric(vals):
    a=[float(x) for x in vals if x is not None]
    return {'n':len(a),'mean_pct':round(sum(a)/len(a),5) if a else None,'median_pct':round(statistics.median(a),5) if a else None,'positive_rate_pct':round(100*sum(x>0 for x in a)/len(a),2) if a else None,'loss_le_minus_1_pct_count':sum(x<=-1 for x in a),'gain_ge_1_pct_count':sum(x>=1 for x in a)}

def aggregate(items):
    return {str(h):metric([((x['horizons'].get(str(h)) or {}).get('directional_return_pct')) for x in items]) for h in HORIZONS}

def build(rows,days=31):
    if not rows:
        return {'schema':SCHEMA,'ok':False,'reason':'NO_COMMITTED_SNAPSHOTS','research_only':True,'live_execution':False}
    end=rows[-1][0]; start=end-dt.timedelta(days=days)
    scoped=[x for x in rows if x[0]>=start]
    obs=[]; last={}
    for i,(t0,r0) in enumerate(rows):
        if t0<start:continue
        for symbol,d in (r0.get('decisions') or {}).items():
            if not isinstance(d,dict) or not d.get('ok'):continue
            p0=price(d); direction=side(d)
            if not p0 or not direction:continue
            klass='QUALIFIED' if d.get('signal_qualified') else 'WAIT_DIRECTIONAL'
            key=(symbol,klass,direction)
            if key in last and (t0-last[key]).total_seconds()<3600:continue
            last[key]=t0
            x={'captured_at':t0.isoformat(),'symbol':symbol,'classification':klass,'direction':direction,'score':f(d.get('score')),'playbook':str(d.get('playbook') or 'UNKNOWN'),'regime':str(d.get('regime') or 'UNKNOWN'),'wait_reason':str(d.get('wait_reason') or 'UNSPECIFIED'),'execution_ready':bool(d.get('execution_ready')),'horizons':{}}
            for h in HORIZONS:
                hit=nearest(rows,i,symbol,t0+dt.timedelta(hours=h))
                if hit:
                    t1,p1=hit; raw=(p1/p0-1)*100; dr=raw if direction=='LONG' else -raw
                    x['horizons'][str(h)]={'observed_at':t1.isoformat(),'directional_return_pct':round(dr,6)}
            obs.append(x)
    q=[x for x in obs if x['classification']=='QUALIFIED']; w=[x for x in obs if x['classification']=='WAIT_DIRECTIONAL']
    groups={}
    for field in ('symbol','direction','playbook','regime'):
        groups[field]={}
        for value in sorted({x[field] for x in q}):groups[field][value]=aggregate([x for x in q if x[field]==value])
    failure=Counter()
    for x in q:
        v=((x['horizons'].get('12') or {}).get('directional_return_pct'))
        if v is not None and v<=-1:
            failure['QUALIFIED_12H_DIRECTIONAL_LOSS_GE_1PCT']+=1
            failure['PLAYBOOK:'+x['playbook']]+=1
            failure['REGIME:'+x['regime']]+=1
    missed=Counter()
    for x in w:
        v=((x['horizons'].get('12') or {}).get('directional_return_pct'))
        if v is not None and v>=1:missed[x['wait_reason']]+=1
    return {'schema':SCHEMA,'ok':True,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'window':{'requested_days':days,'start_at':start.isoformat(),'end_at':end.isoformat(),'snapshot_rows_in_window':len(scoped)},'product_contract':{'canonical_horizon':'4-12H','analyst_only':True,'live_execution':False},'research_only':True,'can_override_production':False,'production_threshold_changed':False,'sampling':'max one observation per symbol/class/direction per hour','counts':{'observations':len(obs),'qualified':len(q),'wait_directional':len(w),'qualified_execution_ready':sum(x['execution_ready'] for x in q)},'qualified':aggregate(q),'wait_directional':aggregate(w),'qualified_breakdown':groups,'wait_reason_counts':dict(Counter(x['wait_reason'] for x in w).most_common()),'failure_attribution_12h':dict(failure.most_common()),'missed_wait_opportunities_12h_ge_1pct_by_reason':dict(missed.most_common()),'latest_observations':obs[-100:]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--history',default='status/history/production-snapshots.jsonl'); ap.add_argument('--output',default='status/monthly-product-audit-latest.json'); ap.add_argument('--days',type=int,default=31); a=ap.parse_args()
    report=build(load(Path(a.history)),a.days); out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({'ok':report.get('ok'),'window':report.get('window'),'counts':report.get('counts'),'qualified':report.get('qualified'),'top_failures':list((report.get('failure_attribution_12h') or {}).items())[:8]},sort_keys=True))
if __name__=='__main__':main()
