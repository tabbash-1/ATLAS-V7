#!/usr/bin/env python3
"""Research-only LONG 3h fail-fast exit overlay.

Accepted combined-shadow LONG signals enter immediately, unchanged. At +3h:
- if the trade is negative, exit at the observed +3h return;
- if the trade is positive, keep the original hold through +12h.

This uses only information available at +3h and does not alter Production
qualification, threshold 68, or the accepted entry shadows. It tests whether
LONG weakness is better handled by early failure management than by delayed
entry or more entry vetoes.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import counterfactual_episode_evaluation as paired

OUT = Path('status/long-3h-failfast-exit-shadow.json')
SCHEMA = 'ATLAS_LONG_3H_FAILFAST_EXIT_SHADOW_V1'
H = 12


def baseline_long(r):
    return r.get('direction') == 'LONG' and combined.candidate_qualified(r)


def overlay_return(r):
    r3 = base.fnum(r.get('return_3h_pct'))
    r12 = base.fnum(r.get('return_12h_pct'))
    if r3 is None or r12 is None:
        return None
    return r3 if r3 <= 0 else r12


def action_at_3h(r):
    r3 = base.fnum(r.get('return_3h_pct'))
    if r3 is None:
        return 'UNKNOWN'
    return 'EXIT_EARLY' if r3 <= 0 else 'HOLD_TO_12H'


def stat(values):
    vals=[float(v) for v in values if v is not None]
    if not vals:
        return {'n':0,'mean_pct':None,'median_pct':None,'win_rate_pct':None}
    return {
        'n':len(vals),
        'mean_pct':round(statistics.mean(vals),4),
        'median_pct':round(statistics.median(vals),4),
        'win_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2),
    }


def lane(rows):
    eps=base.independent([r for r in rows if baseline_long(r)],H)
    mature=[r for r in eps if base.fnum(r.get('return_3h_pct')) is not None and base.fnum(r.get('return_12h_pct')) is not None]
    baseline=[base.fnum(r.get('return_12h_pct')) for r in mature]
    candidate=[overlay_return(r) for r in mature]
    early=[r for r in mature if action_at_3h(r)=='EXIT_EARLY']
    held=[r for r in mature if action_at_3h(r)=='HOLD_TO_12H']
    bs,cs=stat(baseline),stat(candidate)
    return {
        'baseline_immediate_hold_12h':bs,
        'candidate_3h_failfast_overlay':cs,
        'comparison':{
            'mean_delta_pct':None if bs['mean_pct'] is None or cs['mean_pct'] is None else round(cs['mean_pct']-bs['mean_pct'],4),
            'win_rate_delta_pct':None if bs['win_rate_pct'] is None or cs['win_rate_pct'] is None else round(cs['win_rate_pct']-bs['win_rate_pct'],2),
        },
        'early_exit_original_12h_outcomes':stat([base.fnum(r.get('return_12h_pct')) for r in early]),
        'early_exit_realized_3h_outcomes':stat([base.fnum(r.get('return_3h_pct')) for r in early]),
        'held_to_12h_outcomes':stat([base.fnum(r.get('return_12h_pct')) for r in held]),
        'coverage':{
            'baseline_independent_episodes':len(eps),
            'mature_with_3h_and_12h':len(mature),
            'early_exits':len(early),'held_to_12h':len(held),
        },
        'episodes':[
            {
                'captured_at':r['captured_at'].isoformat(),'symbol':r['symbol'],'score':r.get('corrected_score'),
                'return_3h_pct':base.fnum(r.get('return_3h_pct')),'return_12h_pct':base.fnum(r.get('return_12h_pct')),
                'action_at_3h':action_at_3h(r),'overlay_return_pct':round(overlay_return(r),4),
            } for r in mature
        ],
    }


def gate(full,train,hold):
    hc=hold['coverage']
    enough=hc['mature_with_3h_and_12h']>=4 and hc['early_exits']>=2 and hc['held_to_12h']>=1
    def improves(x):
        cmp=x['comparison']; early12=x['early_exit_original_12h_outcomes']
        return bool(
            cmp['mean_delta_pct'] is not None and cmp['mean_delta_pct']>0
            and cmp['win_rate_delta_pct'] is not None and cmp['win_rate_delta_pct']>=0
            and early12['mean_pct'] is not None and early12['mean_pct']<0
        )
    return enough, bool(enough and improves(full) and improves(train) and improves(hold))


def run(path=base.SRC):
    snaps=base.load_snapshots(path); prices=base.build_price_series(snaps)
    rows,excluded=base.flatten(snaps); base.settle(rows,prices); hourly=base.hourly_dedupe(rows)
    train_rows,hold_rows,cutoff=paired.split_60_40(hourly)
    full=lane(hourly); train=lane(train_rows); hold=lane(hold_rows)
    enough,passed=gate(full,train,hold)
    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'hypothesis':'For accepted combined-shadow LONG trades, an executable +3h fail-fast exit on negative mark reduces loss without sacrificing the positive +3h continuation cohort.',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'full':full,'train':train,'holdout':hold,
        'holdout_enough_evidence_for_gate':enough,
        'research_decision':'ADVANCE_LONG_3H_FAILFAST_TO_PROSPECTIVE_SHADOW' if passed else 'KEEP_LONG_3H_FAILFAST_DIAGNOSTIC_ONLY',
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'combined_shadow_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'full':{k:v for k,v in r['full'].items() if k!='episodes'},'train':{k:v for k,v in r['train'].items() if k!='episodes'},'holdout':{k:v for k,v in r['holdout'].items() if k!='episodes'},'holdout_enough_evidence_for_gate':r['holdout_enough_evidence_for_gate'],'research_decision':r['research_decision'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
