#!/usr/bin/env python3
"""Out-of-sample validation for ATLAS provisional Swing quality.

Only post-calibration WAIT decisions are eligible. Repeated observations of the
same symbol/direction/obstacle inside 12h are collapsed into one independent
episode before validation. Nothing here changes Production.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCHEMA = 'ATLAS_SWING_QUALITY_FORWARD_VALIDATION_V2_INDEPENDENT_EPISODES'
CALIBRATION_CUTOFF = '2026-08-25T10:51:50.722660+00:00'
EPISODE_GAP_HOURS = 12
PRELIMINARY_TARGET_HIGH_EPISODES = 10
STRONG_TARGET_HIGH_EPISODES = 30

POSITIVE_COMBOS = {
    'ETHUSDT|LONG|VERY_CLOSE','BNBUSDT|LONG|VERY_CLOSE',
    'BTCUSDT|LONG|VERY_CLOSE','SOLUSDT|LONG|VERY_CLOSE',
}
NEGATIVE_COMBOS = {'HYPEUSDT|SHORT|VERY_CLOSE','DOGEUSDT|SHORT|VERY_CLOSE'}


def _dt(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except ValueError:return None


def _f(v):
    try:
        x=float(v);return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None


def _combo(row):
    return '|'.join((str(row.get('symbol') or 'UNKNOWN').upper(),str(row.get('candidate_direction') or 'NONE').upper(),str(((row.get('score_attribution') or {}).get('obstacle_reason') or 'NONE')).upper()))


def _tier(combo):
    if combo in POSITIVE_COMBOS:return 'PROVISIONAL_POSITIVE'
    if combo in NEGATIVE_COMBOS:return 'PROVISIONAL_NEGATIVE'
    return 'NEUTRAL'


def _summary(vals):
    vals=[x for x in (_f(v) for v in vals) if x is not None]
    if not vals:return {'n':0,'positive_rate_pct':None,'mean_pct':None,'median_pct':None}
    n=len(vals)
    return {'n':n,'positive_rate_pct':round(100*sum(v>0 for v in vals)/n,2),'mean_pct':round(sum(vals)/n,4),'median_pct':round(statistics.median(vals),4)}


def _independent(rows):
    grouped=defaultdict(list)
    for r in rows:
        grouped[r['_combo']].append(r)
    out=[];gap=timedelta(hours=EPISODE_GAP_HOURS)
    for _,items in grouped.items():
        items.sort(key=lambda r:r['_wait_at'])
        last=None
        for r in items:
            if last is None or r['_wait_at']-last>=gap:
                out.append(r);last=r['_wait_at']
    out.sort(key=lambda r:r['_wait_at'])
    return out


def build_report(payload,cutoff=CALIBRATION_CUTOFF,preliminary_target=PRELIMINARY_TARGET_HIGH_EPISODES,strong_target=STRONG_TARGET_HIGH_EPISODES):
    cutoff_dt=_dt(cutoff);assert cutoff_dt is not None
    raw=[]
    for r in list((payload or {}).get('records') or []):
        d=str(r.get('candidate_direction') or 'NONE').upper();score=_f(r.get('score'));t=_dt(r.get('wait_at'))
        if d not in ('LONG','SHORT') or score is None or not 60<=score<68 or t is None or t<=cutoff_dt:continue
        x=dict(r);x['_combo']=_combo(r);x['_tier']=_tier(x['_combo']);x['_wait_at']=t;raw.append(x)
    episodes=_independent(raw)
    by_tier=defaultdict(list);by_combo=defaultdict(list)
    for r in episodes:by_tier[r['_tier']].append(r);by_combo[r['_combo']].append(r)
    def horizons(rows):return {h:_summary(((r.get('horizons') or {}).get(h) or {}).get('directional_return_pct') for r in rows) for h in ('12h','24h')}
    tiers={}
    for tier in ('PROVISIONAL_POSITIVE','NEUTRAL','PROVISIONAL_NEGATIVE'):
        rs=by_tier.get(tier,[]);hs=horizons(rs);n12=hs['12h']['n']
        tiers[tier]={'independent_episodes_after_cutoff':len(rs),'horizons':hs,'preliminary_target_12h':preliminary_target,'strong_target_12h':strong_target,'remaining_to_preliminary_12h':max(0,preliminary_target-n12),'remaining_to_strong_12h':max(0,strong_target-n12)}
    combos={k:{'independent_episodes_after_cutoff':len(v),'horizons':horizons(v)} for k,v in sorted(by_combo.items())}
    p12=tiers['PROVISIONAL_POSITIVE']['horizons']['12h'];n12=tiers['PROVISIONAL_NEGATIVE']['horizons']['12h']
    positive_ok=(p12['positive_rate_pct'] is not None and p12['positive_rate_pct']>=60 and p12['mean_pct'] is not None and p12['mean_pct']>0)
    separation_ok=(n12['n']==0 or n12['mean_pct'] is None or p12['mean_pct'] is None or p12['mean_pct']>n12['mean_pct'])
    if p12['n']>=strong_target:
        status='STRONG_SAMPLE_REVIEW_ONLY' if positive_ok and separation_ok else 'STRONG_SAMPLE_FAILED_OR_WEAK'
    elif p12['n']>=preliminary_target:
        status='PRELIMINARY_VALIDATED_REVIEW_ONLY' if positive_ok and separation_ok else 'PRELIMINARY_FAILED_OR_WEAK'
    else:status='COLLECTING_INDEPENDENT_EPISODES'
    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),'calibration_cutoff':cutoff,'episode_gap_hours':EPISODE_GAP_HOURS,
        'methodology':'Strict out-of-sample validation using only post-cutoff 60-67 WAIT decisions, de-correlated into one observation per 12h combo episode.',
        'raw_eligible_records_after_cutoff':len(raw),'independent_episodes_after_cutoff':len(episodes),'independence_ratio_pct':round(100*len(episodes)/len(raw),2) if raw else None,
        'tiers':tiers,'combos':combos,
        'promotion_gate':{'status':status,'production_change_allowed':False,'preliminary_target_independent_high_episodes':preliminary_target,'strong_target_independent_high_episodes':strong_target,'observed_positive_tier_12h':p12,'observed_negative_tier_12h':n12},
        'production_threshold':68,'production_threshold_changed':False,'production_score_adjustment':0,'auto_promotion_enabled':False,'research_only':True,
    }


def main():
    p=argparse.ArgumentParser();p.add_argument('--wait-outcomes',default='status/wait-outcomes.json');p.add_argument('--output',default='status/swing-quality-forward-validation.json');p.add_argument('--cutoff',default=CALIBRATION_CUTOFF);a=p.parse_args()
    report=build_report(json.loads(Path(a.wait_outcomes).read_text()),a.cutoff)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'raw':report['raw_eligible_records_after_cutoff'],'episodes':report['independent_episodes_after_cutoff'],'gate':report['promotion_gate']['status']},sort_keys=True))
if __name__=='__main__':main()
