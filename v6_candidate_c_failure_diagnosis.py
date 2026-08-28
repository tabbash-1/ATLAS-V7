#!/usr/bin/env python3
"""Diagnose why frozen Candidate C helps downside but fails as a ranker.

Research-only. Uses the same chronological 30% holdout and does not create a new
Production score. It attributes Candidate C's frozen deltas to observed 12h
outcomes and tests whether the components are more suitable as risk vetoes than
ranking bonuses.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from v6_shadow_replay import independent, ret, baseline

SRC = Path('status/wait-outcomes.json')
OUT = Path('status/v6-candidate-c-failure-diagnosis.json')
H = '12h'


def f(v):
    try: return float(v)
    except (TypeError, ValueError): return None


def attrs(r):
    a = r.get('score_attribution') or {}
    rv = f(r.get('relative_volume'))
    votes = f(r.get('direction_votes'))
    fut = f(a.get('futures_adjustment')) or 0.0
    obs = str(r.get('obstacle') or r.get('obstacle_reason') or a.get('obstacle_reason') or '').upper()
    rs = str(a.get('relative_strength_reason') or r.get('relative_strength_reason') or '').upper()
    return rv, votes, fut, obs, rs


def flags(r):
    rv, votes, fut, obs, rs = attrs(r)
    return {
        'VOLUME_070_099': rv is not None and 0.70 <= rv < 1.0,
        'VOLUME_050_069': rv is not None and 0.50 <= rv < 0.70,
        'VOLUME_030_049': rv is not None and 0.30 <= rv < 0.50,
        'VOLUME_015_029': rv is not None and 0.15 <= rv < 0.30,
        'VOLUME_GTE_100': rv is not None and rv >= 1.0,
        'FOUR_DIRECTION_VOTES': votes is not None and votes >= 4,
        'FUTURES_ABS_GT_2': abs(fut) > 2,
        'OBSTACLE_CLOSE': 'CLOSE_PRIOR_STRUCTURE' in obs and 'VERY_CLOSE' not in obs,
        'OBSTACLE_VERY_CLOSE': 'VERY_CLOSE_PRIOR_STRUCTURE' in obs,
        'RS_ALIGNED_STRONG': rs == 'ALIGNED_STRONG',
        'RS_OPPOSED_STRONG': rs == 'OPPOSED_STRONG',
    }


def metrics(vals):
    vals = [x for x in vals if x is not None]
    if not vals: return {'n': 0}
    s = sorted(vals)
    n = len(s)
    return {
        'n': n,
        'mean_pct': round(sum(s)/n, 4),
        'median_pct': round(s[n//2] if n % 2 else (s[n//2-1]+s[n//2])/2, 4),
        'win_rate_pct': round(100*sum(x>0 for x in s)/n, 2),
        'large_loss_rate_pct': round(100*sum(x<=-2 for x in s)/n, 2),
    }


def main():
    raw = json.loads(SRC.read_text()).get('records') or []
    eps = sorted(independent(raw), key=lambda r: r.get('_episode_time') or '')
    cut = max(1, int(len(eps)*0.70))
    test = [r for r in eps[cut:] if ret(r,H) is not None]

    by_flag = defaultdict(lambda: {'flagged': [], 'not_flagged': []})
    for r in test:
        y = ret(r,H)
        for name,on in flags(r).items():
            by_flag[name]['flagged' if on else 'not_flagged'].append(y)

    diag = {}
    for name,g in sorted(by_flag.items()):
        fm, nm = metrics(g['flagged']), metrics(g['not_flagged'])
        risk_lift = None
        if fm.get('n') and nm.get('n'):
            risk_lift = round((fm.get('large_loss_rate_pct',0)-nm.get('large_loss_rate_pct',0)),2)
        diag[name] = {'flagged':fm,'not_flagged':nm,'large_loss_risk_lift_pp':risk_lift}

    # Baseline top-half only: where a veto would actually matter to current V6 ranking.
    ranked = sorted(test, key=baseline, reverse=True)
    top = ranked[:max(5, len(ranked)//2)]
    veto_diag = {}
    for name in diag:
        bad = [ret(r,H) for r in top if flags(r).get(name)]
        keep = [ret(r,H) for r in top if not flags(r).get(name)]
        bm, km = metrics(bad), metrics(keep)
        veto_diag[name] = {
            'would_veto': bm,
            'would_keep': km,
            'coverage_removed_pct': round(100*len(bad)/len(top),2) if top else 0,
        }

    # Only nominate a component for a future PREDECLARED veto test; do not apply it.
    nominees=[]
    for name,d in veto_diag.items():
        bad=d['would_veto']; keep=d['would_keep']
        if bad.get('n',0) >= 3 and keep.get('n',0) >= 3:
            risk_gap=(bad.get('large_loss_rate_pct',0)-keep.get('large_loss_rate_pct',0))
            mean_gap=(keep.get('mean_pct',0)-bad.get('mean_pct',0))
            if risk_gap >= 15 and mean_gap > 0:
                nominees.append((risk_gap,mean_gap,name))
    nominees.sort(reverse=True)

    report={
      'schema':'ATLAS_V6_CANDIDATE_C_FAILURE_DIAGNOSIS_V1',
      'generated_at':datetime.now(timezone.utc).isoformat(),
      'holdout_12h_n':len(test),
      'candidate_c_status':'REJECTED_AS_RANKER_AND_GENERAL_OVERLAY',
      'component_outcome_diagnostics':diag,
      'baseline_top_half_veto_diagnostics':veto_diag,
      'future_veto_test_nominee': nominees[0][2] if nominees else None,
      'nominee_rule':'Nomination only. A separate predeclared equal-coverage veto replay is required before any prospective shadow use.',
      'guardrails':{'research_only':True,'production_threshold_changed':False,'production_score_changed':False,'auto_promotion_enabled':False,'candidate_c_promoted':False},
    }
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'holdout_12h_n':len(test),'nominee':report['future_veto_test_nominee']}))

if __name__=='__main__': main()
