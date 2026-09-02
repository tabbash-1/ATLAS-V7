#!/usr/bin/env python3
"""Prospective ATLAS 4H direction/regime validation.

Selection uses decision-time Production snapshots only. The manifest is created
once and locks the cohort start before any later 4H outcome is evaluated.
Research/shadow only; no Production or execution authority.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from pathlib import Path

SCHEMA='ATLAS_PROSPECTIVE_DIRECTION_GUARDRAIL_V1_4H'
MANIFEST_SCHEMA='ATLAS_PROSPECTIVE_DIRECTION_GUARDRAIL_MANIFEST_V1'
START_POLICY='MANIFEST_CREATION_TIME_ONLY_NO_PRESTART_ROWS'
MIN_MATURED=30
TARGET_HOURS=4
MAX_LAG_MIN=50
RULES={
  'target_horizon_hours':4,
  'minimum_matured_per_group':30,
  'groups':{
    'SHORT_TREND_DOWN_4H':{'classification':'QUALIFIED','direction':'SHORT','regime':'TREND_DOWN'},
    'LONG_TREND_UP_CAUTION_4H':{'classification':'QUALIFIED','direction':'LONG','regime':'TREND_UP'},
  },
  'short_support_thresholds':{'mean_pct_min':0.20,'positive_rate_pct_min':55.0},
  'long_caution_thresholds':{'mean_pct_max':0.0,'positive_rate_pct_max':45.0},
  'sampling':'AT_MOST_ONE_ENTRY_PER_GROUP_SYMBOL_PER_60_MINUTES',
  'missing_outcome_policy':'EXCLUDE_NEVER_ZERO_FILL',
  'start_policy':START_POLICY,
  'promotion_policy':'NO_PRODUCTION_CHANGE_FROM_THIS_REPORT_ALONE',
}

def now():return dt.datetime.now(dt.timezone.utc)
def parse_ts(v):
    try:return dt.datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(dt.timezone.utc)
    except Exception:return None
def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
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
def canonical_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def manifest_body(start_at):
    return {'schema':MANIFEST_SCHEMA,'cohort_start_at':start_at,'rules':RULES,'research_only':True,'shadow_only':True,'live_execution':False,'can_override_production':False,'can_change_threshold':False}
def load_or_create_manifest(path):
    if path.exists():
        m=json.loads(path.read_text())
        body={k:m.get(k) for k in ('schema','cohort_start_at','rules','research_only','shadow_only','live_execution','can_override_production','can_change_threshold')}
        if m.get('manifest_hash')!=canonical_hash(body) or body.get('rules')!=RULES:raise RuntimeError('MANIFEST_LOCK_MISMATCH')
        return m
    body=manifest_body(now().isoformat()); m={**body,'manifest_hash':canonical_hash(body)}; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(m,indent=2,sort_keys=True)); return m
def load_history(path):
    out=[]
    if not path.exists():return out
    for line in path.read_text(errors='replace').splitlines():
        try:r=json.loads(line)
        except Exception:continue
        t=parse_ts(r.get('captured_at'))
        if t:out.append((t,r))
    return sorted(out,key=lambda x:x[0])
def group_for(d):
    if not d.get('signal_qualified'):return None
    side=direction(d); regime=str(d.get('regime') or '')
    if side=='SHORT' and regime=='TREND_DOWN':return 'SHORT_TREND_DOWN_4H'
    if side=='LONG' and regime=='TREND_UP':return 'LONG_TREND_UP_CAUTION_4H'
    return None
def freeze_entries(rows,manifest,cohort_path):
    start=parse_ts(manifest['cohort_start_at']); existing=[]
    if cohort_path.exists():
        for line in cohort_path.read_text(errors='replace').splitlines():
            try:existing.append(json.loads(line))
            except Exception:pass
    if any(x.get('manifest_hash')!=manifest['manifest_hash'] for x in existing):raise RuntimeError('COHORT_MANIFEST_HASH_MISMATCH')
    ids={x.get('id') for x in existing}; last={}
    for x in existing:
        t=parse_ts(x.get('captured_at'))
        if t:last[(x.get('group'),x.get('symbol'))]=max(last.get((x.get('group'),x.get('symbol')),t),t)
    added=[]
    for t,r in rows:
        if t<start:continue
        for symbol,d in (r.get('decisions') or {}).items():
            if not isinstance(d,dict) or not d.get('ok'):continue
            g=group_for(d); p=price(d)
            if not g or not p:continue
            key=(g,symbol); prev=last.get(key)
            if prev and (t-prev).total_seconds()<3600:continue
            rid=hashlib.sha256(f"{manifest['manifest_hash']}|{g}|{symbol}|{t.isoformat()}".encode()).hexdigest()[:24]
            if rid in ids:continue
            row={'id':rid,'manifest_hash':manifest['manifest_hash'],'group':g,'symbol':symbol,'captured_at':t.isoformat(),'direction':direction(d),'regime':d.get('regime'),'playbook':d.get('playbook'),'score':f(d.get('score')),'entry_price':p,'outcome_known_at_freeze':False,'research_only':True,'shadow_only':True}
            existing.append(row); added.append(row); ids.add(rid); last[key]=t
    cohort_path.parent.mkdir(parents=True,exist_ok=True)
    cohort_path.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in existing))
    return existing,added
def nearest(rows,symbol,target):
    limit=target+dt.timedelta(minutes=MAX_LAG_MIN)
    for t,r in rows:
        if t<target:continue
        if t>limit:return None
        p=price(((r.get('decisions') or {}).get(symbol) or {}))
        if p:return t,p
    return None
def metrics(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {'n':0,'mean_pct':None,'positive_rate_pct':None}
    return {'n':len(vals),'mean_pct':round(sum(vals)/len(vals),6),'positive_rate_pct':round(100*sum(x>0 for x in vals)/len(vals),4)}
def evaluate(rows,cohort,manifest):
    by={g:[] for g in RULES['groups']}
    for x in cohort:
        t=parse_ts(x['captured_at']); hit=nearest(rows,x['symbol'],t+dt.timedelta(hours=TARGET_HOURS))
        if not hit:continue
        _,p1=hit; p0=float(x['entry_price']); market=(p1/p0-1)*100; dr=market if x['direction']=='LONG' else -market
        by[x['group']].append(dr)
    gm={g:metrics(v) for g,v in by.items()}; s=gm['SHORT_TREND_DOWN_4H']; l=gm['LONG_TREND_UP_CAUTION_4H']
    short_ready=s['n']>=MIN_MATURED; long_ready=l['n']>=MIN_MATURED
    short_supported=bool(short_ready and s['mean_pct']>=RULES['short_support_thresholds']['mean_pct_min'] and s['positive_rate_pct']>=RULES['short_support_thresholds']['positive_rate_pct_min'])
    long_caution=bool(long_ready and l['mean_pct']<=RULES['long_caution_thresholds']['mean_pct_max'] and l['positive_rate_pct']<=RULES['long_caution_thresholds']['positive_rate_pct_max'])
    return {'schema':SCHEMA,'generated_at':now().isoformat(),'manifest_hash':manifest['manifest_hash'],'cohort_start_at':manifest['cohort_start_at'],'research_only':True,'shadow_only':True,'live_execution':False,'can_override_production':False,'can_change_threshold':False,'target_horizon_hours':4,'groups':gm,'sample_progress':{g:{'matured':gm[g]['n'],'target':MIN_MATURED,'remaining':max(0,MIN_MATURED-gm[g]['n'])} for g in gm},'claims':{'short_4h_edge_supported':short_supported,'long_trend_up_caution_supported':long_caution,'claims_ready':short_ready and long_ready},'promotion_policy':RULES['promotion_policy']}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--history',default='status/history/production-snapshots.jsonl'); ap.add_argument('--manifest',default='status/prospective-direction-guardrail-manifest.json'); ap.add_argument('--cohort',default='status/history/prospective-direction-guardrail-cohort.jsonl'); ap.add_argument('--report',default='status/prospective-direction-guardrail-latest.json'); a=ap.parse_args()
    m=load_or_create_manifest(Path(a.manifest)); rows=load_history(Path(a.history)); cohort,added=freeze_entries(rows,m,Path(a.cohort)); report=evaluate(rows,cohort,m); Path(a.report).write_text(json.dumps(report,indent=2,sort_keys=True)); print(json.dumps({'manifest_hash':m['manifest_hash'],'added':len(added),'cohort':len(cohort),'progress':report['sample_progress'],'claims':report['claims']},sort_keys=True))
if __name__=='__main__':main()
