#!/usr/bin/env python3
"""Research-only LONG delayed-confirmation entry shadow.

For accepted combined-shadow LONG signals:
- baseline: enter immediately at the signal and observe +12h return.
- candidate: wait 3h. Enter only when the +3h price is ABOVE the original
  signal price, then measure return from the +3h entry to the original +12h
  horizon (a 9h post-confirmation hold).

This is executable without lookahead: the 3h condition is known at entry time.
Historical +3h/+12h prices are reconstructed from already-settled snapshot data.
No Production scoring or threshold is changed.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import counterfactual_episode_evaluation as paired

OUT = Path('status/long-3h-confirmation-entry-shadow.json')
SCHEMA = 'ATLAS_LONG_3H_CONFIRMATION_ENTRY_SHADOW_V1'
H = 12


def baseline_long(r):
    return r.get('direction') == 'LONG' and combined.candidate_qualified(r)


def delayed_return(r):
    r3 = base.fnum(r.get('return_3h_pct'))
    r12 = base.fnum(r.get('return_12h_pct'))
    if r3 is None or r12 is None:
        return None
    p3 = 1.0 + r3 / 100.0
    p12 = 1.0 + r12 / 100.0
    if p3 <= 0:
        return None
    return (p12 / p3 - 1.0) * 100.0


def confirmed(r):
    r3 = base.fnum(r.get('return_3h_pct'))
    return r3 is not None and r3 > 0


def stat(values):
    values=[float(v) for v in values if v is not None]
    if not values:
        return {'n':0,'mean_pct':None,'median_pct':None,'win_rate_pct':None}
    return {
        'n':len(values),
        'mean_pct':round(statistics.mean(values),4),
        'median_pct':round(statistics.median(values),4),
        'win_rate_pct':round(100*sum(v>0 for v in values)/len(values),2),
    }


def episode_set(rows):
    return base.independent([r for r in rows if baseline_long(r)],H)


def lane(rows):
    eps=episode_set(rows)
    mature=[r for r in eps if base.fnum(r.get('return_3h_pct')) is not None and base.fnum(r.get('return_12h_pct')) is not None]
    accepted=[r for r in mature if confirmed(r)]
    rejected=[r for r in mature if not confirmed(r)]
    baseline_returns=[base.fnum(r.get('return_12h_pct')) for r in mature]
    candidate_returns=[delayed_return(r) for r in accepted]
    rejected_returns=[base.fnum(r.get('return_12h_pct')) for r in rejected]
    return {
        'baseline_immediate_12h':stat(baseline_returns),
        'candidate_confirmed_3h_to_12h':stat(candidate_returns),
        'rejected_at_3h_original_12h_outcomes':stat(rejected_returns),
        'coverage':{
            'baseline_independent_episodes':len(eps),
            'mature_with_3h_and_12h':len(mature),
            'confirmed_entries':len(accepted),
            'rejected_entries':len(rejected),
            'confirmation_rate_pct':None if not mature else round(100*len(accepted)/len(mature),2),
        },
        'mean_delta_vs_immediate_pct':None if not baseline_returns or not candidate_returns else round(statistics.mean(candidate_returns)-statistics.mean(baseline_returns),4),
        'episodes':[
            {
                'captured_at':r['captured_at'].isoformat(),'symbol':r['symbol'],'score':r.get('corrected_score'),
                'return_3h_pct':base.fnum(r.get('return_3h_pct')),
                'return_12h_pct':base.fnum(r.get('return_12h_pct')),
                'confirmed_at_3h':confirmed(r),
                'delayed_3h_to_12h_return_pct':None if not confirmed(r) else round(delayed_return(r),4),
            }
            for r in mature
        ],
    }


def gate(full,train,hold):
    # This is a timing rule, not a same-entry counterfactual. Require temporal
    # consistency and enough confirmed/rejected observations in holdout.
    hc=hold['coverage']
    enough=hc['mature_with_3h_and_12h']>=4 and hc['confirmed_entries']>=2 and hc['rejected_entries']>=1
    def improves(x):
        b=x['baseline_immediate_12h']; c=x['candidate_confirmed_3h_to_12h']; rej=x['rejected_at_3h_original_12h_outcomes']
        return bool(
            b['mean_pct'] is not None and c['mean_pct'] is not None and c['mean_pct']>b['mean_pct']
            and c['win_rate_pct'] is not None and b['win_rate_pct'] is not None and c['win_rate_pct']>=b['win_rate_pct']
            and rej['mean_pct'] is not None and rej['mean_pct']<0
        )
    passed=bool(enough and improves(full) and improves(train) and improves(hold))
    return enough,passed


def run(path=base.SRC):
    snaps=base.load_snapshots(path); prices=base.build_price_series(snaps)
    rows,excluded=base.flatten(snaps); base.settle(rows,prices); hourly=base.hourly_dedupe(rows)
    # Split BEFORE selecting independent episodes in each lane, matching our
    # temporal validation convention. No candidate-specific de-correlation is
    # used, so episode substitution cannot favor the candidate.
    train_rows,hold_rows,cutoff=paired.split_60_40(hourly)
    full=lane(hourly); train=lane(train_rows); hold=lane(hold_rows)
    enough,passed=gate(full,train,hold)
    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'hypothesis':'Accepted LONG signals that remain above their signal price after 3h have better executable continuation than immediate LONG entry, while 3h-negative signals are poor original 12h trades.',
        'coverage':{'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'cutoff_at':cutoff.isoformat() if cutoff else None,'excluded':excluded},
        'full':full,'train':train,'holdout':hold,
        'holdout_enough_evidence_for_gate':enough,
        'research_decision':'ADVANCE_LONG_3H_CONFIRMATION_TO_PROSPECTIVE_SHADOW' if passed else 'REJECT_OR_KEEP_DIAGNOSTIC_LONG_3H_CONFIRMATION',
        'production_change_recommended':False,
        'guardrails':{'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'combined_shadow_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run(); OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'schema':r['schema'],'coverage':r['coverage'],'full':{k:v for k,v in r['full'].items() if k!='episodes'},'train':{k:v for k,v in r['train'].items() if k!='episodes'},'holdout':{k:v for k,v in r['holdout'].items() if k!='episodes'},'holdout_enough_evidence_for_gate':r['holdout_enough_evidence_for_gate'],'research_decision':r['research_decision'],'guardrails':r['guardrails']},sort_keys=True))

if __name__=='__main__': main()
