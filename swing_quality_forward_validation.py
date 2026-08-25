#!/usr/bin/env python3
"""Out-of-sample validation for ATLAS combo-calibrated Swing research quality.

The calibration sample is frozen. Only WAIT records whose wait_at is strictly
after CALIBRATION_CUTOFF are eligible here. This module never changes Production
score, threshold, geometry, or execution eligibility.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 'ATLAS_SWING_QUALITY_FORWARD_VALIDATION_V1'
CALIBRATION_CUTOFF = '2026-08-25T10:51:50.722660+00:00'
TARGET_NEW_CASES_PER_TIER = 30

HIGH_COMBOS = {
    'ETHUSDT|LONG|VERY_CLOSE',
    'BNBUSDT|LONG|VERY_CLOSE',
    'BTCUSDT|LONG|VERY_CLOSE',
    'SOLUSDT|LONG|VERY_CLOSE',
}
LOW_COMBOS = {
    'HYPEUSDT|SHORT|VERY_CLOSE',
    'DOGEUSDT|SHORT|VERY_CLOSE',
}


def _dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except ValueError:
        return None


def _f(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _combo(row):
    symbol=str(row.get('symbol') or 'UNKNOWN').upper()
    direction=str(row.get('candidate_direction') or 'NONE').upper()
    obstacle=str(((row.get('score_attribution') or {}).get('obstacle_reason') or 'NONE')).upper()
    return f'{symbol}|{direction}|{obstacle}'


def _tier(combo):
    if combo in HIGH_COMBOS:
        return 'HIGH'
    if combo in LOW_COMBOS:
        return 'LOW'
    return 'NEUTRAL'


def _summary(vals):
    vals=[x for x in (_f(v) for v in vals) if x is not None]
    if not vals:
        return {'n':0,'positive_rate_pct':None,'mean_pct':None,'median_pct':None}
    n=len(vals)
    return {
        'n':n,
        'positive_rate_pct':round(100*sum(v>0 for v in vals)/n,2),
        'mean_pct':round(sum(vals)/n,4),
        'median_pct':round(statistics.median(vals),4),
    }


def build_report(payload, cutoff=CALIBRATION_CUTOFF, target=TARGET_NEW_CASES_PER_TIER):
    cutoff_dt=_dt(cutoff)
    assert cutoff_dt is not None
    all_rows=list((payload or {}).get('records') or [])
    eligible=[]
    for r in all_rows:
        direction=str(r.get('candidate_direction') or 'NONE').upper()
        score=_f(r.get('score'))
        wait_at=_dt(r.get('wait_at'))
        if direction not in ('LONG','SHORT') or score is None or not (60 <= score < 68):
            continue
        if wait_at is None or wait_at <= cutoff_dt:
            continue
        x=dict(r)
        x['_combo']=_combo(r)
        x['_tier']=_tier(x['_combo'])
        eligible.append(x)

    by_tier=defaultdict(list)
    by_combo=defaultdict(list)
    for r in eligible:
        by_tier[r['_tier']].append(r)
        by_combo[r['_combo']].append(r)

    def horizons(rows):
        return {
            h:_summary(((r.get('horizons') or {}).get(h) or {}).get('directional_return_pct') for r in rows)
            for h in ('12h','24h')
        }

    tier_report={}
    for tier in ('HIGH','NEUTRAL','LOW'):
        rows=by_tier.get(tier,[])
        hs=horizons(rows)
        n12=hs['12h']['n']
        tier_report[tier]={
            'records_after_cutoff':len(rows),
            'horizons':hs,
            'target_new_cases_12h':int(target),
            'remaining_to_target_12h':max(0,int(target)-n12),
            'validation_ready_12h':n12>=int(target),
        }

    combo_report={k:{'records_after_cutoff':len(v),'horizons':horizons(v)} for k,v in sorted(by_combo.items())}

    high12=tier_report['HIGH']['horizons']['12h']
    low12=tier_report['LOW']['horizons']['12h']
    promotion_gate={
        'status':'COLLECTING',
        'production_change_allowed':False,
        'requirements':{
            'high_tier_new_12h_cases_min':int(target),
            'high_tier_positive_rate_min_pct':60.0,
            'high_tier_mean_return_must_be_positive':True,
            'low_tier_should_underperform_high_tier':True,
        },
        'observed':{
            'high_n_12h':high12['n'],
            'high_positive_rate_12h_pct':high12['positive_rate_pct'],
            'high_mean_12h_pct':high12['mean_pct'],
            'low_n_12h':low12['n'],
            'low_positive_rate_12h_pct':low12['positive_rate_pct'],
            'low_mean_12h_pct':low12['mean_pct'],
        },
    }
    enough=high12['n']>=int(target)
    high_ok=(high12['positive_rate_pct'] is not None and high12['positive_rate_pct']>=60 and
             high12['mean_pct'] is not None and high12['mean_pct']>0)
    separation_ok=(low12['n']==0 or high12['mean_pct'] is None or low12['mean_pct'] is None or high12['mean_pct']>low12['mean_pct'])
    if enough and high_ok and separation_ok:
        promotion_gate['status']='RESEARCH_VALIDATED_REVIEW_ONLY'
    elif enough:
        promotion_gate['status']='RESEARCH_VALIDATION_FAILED_OR_WEAK'

    return {
        'schema':SCHEMA,
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'calibration_cutoff':cutoff,
        'methodology':'Strict out-of-sample forward validation: only post-cutoff recorded WAIT decisions are counted; frozen calibration rows are excluded.',
        'eligible_records_after_cutoff':len(eligible),
        'tiers':tier_report,
        'combos':combo_report,
        'promotion_gate':promotion_gate,
        'production_threshold':68,
        'production_threshold_changed':False,
        'production_score_adjustment':0,
        'auto_promotion_enabled':False,
        'research_only':True,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--wait-outcomes',default='status/wait-outcomes.json')
    p.add_argument('--output',default='status/swing-quality-forward-validation.json')
    p.add_argument('--cutoff',default=CALIBRATION_CUTOFF)
    p.add_argument('--target',type=int,default=TARGET_NEW_CASES_PER_TIER)
    args=p.parse_args()
    payload=json.loads(Path(args.wait_outcomes).read_text())
    report=build_report(payload,args.cutoff,args.target)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'eligible':report['eligible_records_after_cutoff'],'gate':report['promotion_gate']['status']},sort_keys=True))


if __name__=='__main__':
    main()
