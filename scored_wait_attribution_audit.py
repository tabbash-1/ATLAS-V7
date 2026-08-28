#!/usr/bin/env python3
"""Research-only attribution audit for remaining V6 scored WAIT decisions."""
from __future__ import annotations

import json, math, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SRC = Path('status/wait-outcomes.json')
OUT = Path('status/scored-wait-attribution-audit.json')
V6_PREFIX = 'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE'
FIX_TAG = 'PARTIAL_VOLUME_TIME_FIX_V1'
SCHEMA = 'ATLAS_SCORED_WAIT_ATTRIBUTION_AUDIT_V1'
THRESHOLD = 68.0
EPISODE_GAP = timedelta(hours=12)
HORIZONS = ('1h','3h','12h','24h')
ALIASES = {'VERY_CLOSE':'VERY_CLOSE_PRIOR_STRUCTURE','CLOSE':'CLOSE_PRIOR_STRUCTURE'}


def fnum(v, default=None):
    try:
        x=float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def parse_time(v):
    try: return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception: return None


def version(r):
    return str((r.get('decision_context') or {}).get('scoring_version') or '').upper()


def obstacle_reason(r):
    x=str((r.get('score_attribution') or {}).get('obstacle_reason') or 'NONE').upper()
    return ALIASES.get(x,x)


def progress_from_timestamp(ts):
    if ts is None: return 1.0
    sec=ts.minute*60+ts.second+ts.microsecond/1_000_000
    return max(0.10,min(1.0,sec/3600.0))


def paced_rv(raw_rv, progress):
    raw=max(0.0,fnum(raw_rv,0.0))
    p=max(0.10,min(1.0,fnum(progress,1.0)))
    return min(4.0,raw/p)


def volume_bonus_v6(rv):
    return min(10.0,max(0.0,(fnum(rv,0.0)-1.0)*10.0))


def round_score(v):
    return int(round(max(0.0,min(100.0,fnum(v,0.0)))))


def corrected_score(r):
    """Replay only the known pre-fix missing partial-hour volume bonus."""
    score=fnum(r.get('score'))
    if score is None: return None
    ver=version(r); attr=r.get('score_attribution') or {}; dc=r.get('decision_context') or {}
    raw_rv=fnum(dc.get('relative_volume'))
    if FIX_TAG in ver or raw_rv is None:
        return {'score':round_score(score),'volume_delta':0.0,'raw_rv':raw_rv,'paced_rv':raw_rv,'progress':1.0 if FIX_TAG in ver else None,'post_fix':FIX_TAG in ver}
    p=progress_from_timestamp(parse_time(r.get('wait_at')))
    paced=paced_rv(raw_rv,p)
    old_bonus=fnum(attr.get('volume_bonus'),volume_bonus_v6(raw_rv))
    new_bonus=volume_bonus_v6(paced)
    delta=max(0.0,new_bonus-old_bonus)
    raw_score=fnum(attr.get('raw_score'),score)
    return {'score':round_score(raw_score+delta),'volume_delta':round(delta,6),'raw_rv':round(raw_rv,6),'paced_rv':round(paced,6),'progress':round(p,6),'post_fix':False}


def hourly_dedupe(rows):
    chosen={}
    for r in sorted(rows,key=lambda x:str(x.get('wait_at') or '')):
        ts=parse_time(r.get('wait_at'))
        if not ts: continue
        key=(str(r.get('symbol') or '').upper(),str(r.get('candidate_direction') or '').upper(),ts.replace(minute=0,second=0,microsecond=0).isoformat())
        chosen.setdefault(key,r)
    return list(chosen.values())


def independent_12h(rows):
    groups=defaultdict(list)
    for r in rows:
        ts=parse_time(r.get('wait_at')); d=str(r.get('candidate_direction') or '').upper(); s=str(r.get('symbol') or '').upper()
        if ts and d in ('LONG','SHORT'): groups[(s,d)].append((ts,r))
    out=[]
    for items in groups.values():
        last=None
        for ts,r in sorted(items,key=lambda x:x[0]):
            if last is None or ts-last>=EPISODE_GAP:
                out.append(r); last=ts
    return sorted(out,key=lambda r:str(r.get('wait_at') or ''))


def directional_value(r,h):
    return fnum((r.get('horizons') or {}).get(h,{}).get('directional_return_pct'))


def stats(rows,h):
    vals=[directional_value(r,h) for r in rows]; vals=[v for v in vals if v is not None]
    if not vals: return {'n':0,'mean_pct':None,'median_pct':None,'win_rate_pct':None}
    return {'n':len(vals),'mean_pct':round(statistics.mean(vals),4),'median_pct':round(statistics.median(vals),4),'win_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2)}


def horizon_report(rows):
    return {h:stats(rows,h) for h in HORIZONS}


def split_stability(rows,h):
    usable=sorted([r for r in rows if directional_value(r,h) is not None],key=lambda r:str(r.get('wait_at') or ''))
    if len(usable)<5: return {'n':len(usable),'eligible':False,'stable_positive':False}
    cut=max(1,min(len(usable)-1,int(len(usable)*0.60)))
    train,hold=stats(usable[:cut],h),stats(usable[cut:],h)
    symbols=sorted({str(r.get('symbol') or '').upper() for r in usable})
    jk=[]
    for s in symbols:
        x=stats([r for r in usable if str(r.get('symbol') or '').upper()!=s],h)
        if x['n']: jk.append(x)
    pos=sum((x.get('mean_pct') or 0)>0 for x in jk); win=sum((x.get('win_rate_pct') or 0)>=50 for x in jk)
    stable=bool(len(usable)>=8 and (train.get('mean_pct') or 0)>0 and (hold.get('mean_pct') or 0)>0 and (hold.get('win_rate_pct') or 0)>=50 and jk and pos==len(jk) and win==len(jk))
    return {'n':len(usable),'eligible':True,'train':train,'holdout':hold,'leave_one_symbol_out':{'tests':len(jk),'positive_mean':pos,'win_rate_ge_50':win,'all_positive_and_win50':bool(jk and pos==len(jk) and win==len(jk))},'stable_positive':stable}


def gap_bucket(r):
    gap=max(0.0,THRESHOLD-fnum(r.get('_corrected_score'),0.0))
    if gap<=2:return '1-2'
    if gap<=4:return '3-4'
    if gap<=8:return '5-8'
    return '>8'


def grouped(rows,keyfn):
    g=defaultdict(list)
    for r in rows:g[str(keyfn(r))].append(r)
    return {k:{'episodes':len(v),'outcomes':horizon_report(v)} for k,v in sorted(g.items())}


def relaxation_delta(r,rule):
    a=r.get('score_attribution') or {}; obs=fnum(a.get('obstacle_adjustment'),0.0) or 0.0; fut=fnum(a.get('futures_adjustment'),0.0) or 0.0; rs=fnum(a.get('relative_strength_adjustment'),0.0) or 0.0; reason=obstacle_reason(r)
    if rule=='REMOVE_CLOSE_OBSTACLE_PENALTY': return -obs if reason=='CLOSE_PRIOR_STRUCTURE' and obs<0 else 0.0
    if rule=='REMOVE_VERY_CLOSE_OBSTACLE_PENALTY': return -obs if reason=='VERY_CLOSE_PRIOR_STRUCTURE' and obs<0 else 0.0
    if rule=='REMOVE_ANY_OBSTACLE_PENALTY': return -obs if obs<0 else 0.0
    if rule=='REMOVE_NEGATIVE_FUTURES_PENALTY': return -fut if fut<0 else 0.0
    if rule=='REMOVE_OPPOSED_RELATIVE_STRENGTH_PENALTY': return -rs if rs<0 else 0.0
    raise KeyError(rule)


def evaluate_relaxation(rows,rule):
    selected=[]
    for r in rows:
        base=fnum(r.get('_corrected_score'))
        if base is None or base>=THRESHOLD: continue
        delta=relaxation_delta(r,rule)
        if delta>0 and round_score(base+delta)>=THRESHOLD:
            x=dict(r); x['_relaxation_delta']=round(delta,4); x['_counterfactual_score']=round_score(base+delta); selected.append(x)
    eps=independent_12h(selected); s12=split_stability(eps,'12h'); s24=split_stability(eps,'24h')
    return {'hourly_crossings':len(selected),'independent_12h_crossings':len(eps),'outcomes':horizon_report(eps),'stability':{'12h':s12,'24h':s24},'production_change_recommended':False,'research_interpretation':'SHADOW_CANDIDATE' if s12.get('stable_positive') or s24.get('stable_positive') else 'KEEP_AS_HYPOTHESIS'}


def audit(payload):
    scored=[]
    for r in payload.get('records') or []:
        if not version(r).startswith(V6_PREFIX) or str(r.get('reason') or '')!='SCORE_BELOW_SIGNAL_THRESHOLD' or str(r.get('candidate_direction') or '').upper() not in ('LONG','SHORT'): continue
        c=corrected_score(r)
        if not c: continue
        x=dict(r); x['_corrected_score']=c['score']; x['_volume_delta']=c['volume_delta']; x['_paced_rv']=c['paced_rv']; x['_raw_rv']=c['raw_rv']; x['_post_volume_fix']=c['post_fix']; scored.append(x)
    hourly=hourly_dedupe(scored); volume_flips=[r for r in hourly if fnum(r.get('_corrected_score'),0)>=THRESHOLD]; remaining=[r for r in hourly if fnum(r.get('_corrected_score'),0)<THRESHOLD]; eps=independent_12h(remaining)
    rules=('REMOVE_CLOSE_OBSTACLE_PENALTY','REMOVE_VERY_CLOSE_OBSTACLE_PENALTY','REMOVE_ANY_OBSTACLE_PENALTY','REMOVE_NEGATIVE_FUTURES_PENALTY','REMOVE_OPPOSED_RELATIVE_STRENGTH_PENALTY')
    relax={rule:evaluate_relaxation(remaining,rule) for rule in rules}
    near=[]
    for r in sorted(remaining,key=lambda x:(THRESHOLD-fnum(x.get('_corrected_score'),0),str(x.get('wait_at') or '')))[:25]:
        a=r.get('score_attribution') or {}
        near.append({'symbol':r.get('symbol'),'wait_at':r.get('wait_at'),'direction':r.get('candidate_direction'),'stored_score':r.get('score'),'corrected_score':r.get('_corrected_score'),'gap_to_68':round(THRESHOLD-fnum(r.get('_corrected_score'),0),3),'volume_fix_delta':r.get('_volume_delta'),'direction_votes':(r.get('decision_context') or {}).get('direction_votes'),'obstacle_reason':obstacle_reason(r),'obstacle_adjustment':a.get('obstacle_adjustment'),'futures_reason':a.get('futures_reason'),'futures_adjustment':a.get('futures_adjustment'),'relative_strength_reason':a.get('relative_strength_reason'),'relative_strength_adjustment':a.get('relative_strength_adjustment'),'12h_directional_return_pct':directional_value(r,'12h'),'24h_directional_return_pct':directional_value(r,'24h')})
    return {'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),'purpose':'Explain remaining V6 scored WAIT after replay-correcting the known partial-hour volume bias using existing outcomes only.','method':{'v6_scope':f'scoring_version starts {V6_PREFIX}','wait_scope':'SCORE_BELOW_SIGNAL_THRESHOLD with LONG/SHORT direction','hourly_dedupe':'earliest symbol/direction observation per UTC hour','outcome_independence':'one symbol/direction episode every 12 hours','volume_replay':'pre-fix only; restore only missing non-negative paced volume bonus','counterfactuals':'relax one negative component at a time; never combine tuning','stability':'60/40 chronological holdout + leave-one-symbol-out; n>=8 and all stability gates required'},'coverage':{'raw_v6_scored_wait_records':len(scored),'hourly_v6_scored_waits':len(hourly),'hourly_volume_fix_crossings':len(volume_flips),'hourly_remaining_after_volume_fix':len(remaining),'independent_12h_remaining':len(eps)},'remaining_wait_outcomes':horizon_report(eps),'remaining_by_gap_to_threshold':grouped(eps,gap_bucket),'remaining_by_direction_votes':grouped(eps,lambda r:(r.get('decision_context') or {}).get('direction_votes','UNKNOWN')),'remaining_by_obstacle':grouped(eps,obstacle_reason),'remaining_by_futures_reason':grouped(eps,lambda r:(r.get('score_attribution') or {}).get('futures_reason','UNKNOWN')),'remaining_by_relative_strength_reason':grouped(eps,lambda r:(r.get('score_attribution') or {}).get('relative_strength_reason','UNKNOWN')),'single_component_counterfactuals':relax,'near_threshold_examples':near,'guardrails':{'research_only':True,'production_threshold':THRESHOLD,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False,'live_execution':False},'next_decision':'Only a single-component relaxation stable on chronological holdout and leave-one-symbol-out may advance to separate shadow; otherwise Production remains unchanged.'}


def main():
    report=audit(json.loads(SRC.read_text()))
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':report['schema'],'coverage':report['coverage'],'shadow_candidates':[k for k,v in report['single_component_counterfactuals'].items() if v['research_interpretation']=='SHADOW_CANDIDATE'],'guardrails':report['guardrails']},sort_keys=True))


if __name__=='__main__': main()
