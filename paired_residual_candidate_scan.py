#!/usr/bin/env python3
"""Scan residual harmful buckets with paired counterfactual methodology.

Candidate universe is deliberately constrained to buckets already identified as
stable harmful after the accepted combined shadow. Each candidate is tested as
ONE isolated veto against the combined baseline using both:
- dynamic opportunity-sequence replay
- fixed-baseline-anchor paired impact
in train and holdout separately.

This is research-only and cannot mutate Production.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as combined
import post_combined_shadow_residual_autopsy as residual
import counterfactual_episode_evaluation as paired

OUT = Path('status/paired-residual-candidate-scan.json')
SCHEMA = 'ATLAS_PAIRED_RESIDUAL_CANDIDATE_SCAN_V1'

# Only factors with clear runtime predicates are eligible for isolated veto
# replay. Compound factors are decoded from the same keymap used by the autopsy.
ELIGIBLE_FACTORS = {
    'direction','obstacle','relative_strength','volume_bin','shadow_score_bin',
    'direction_x_obstacle','direction_x_rs','direction_x_volume','direction_x_score',
    'rs_x_obstacle','volume_x_obstacle','score_x_rs','score_x_obstacle',
}


def combined_baseline(r):
    return combined.candidate_qualified(r)


def bucket_match(r, factor, bucket):
    return residual.keymap(r).get(factor) == bucket


def candidate_pred(factor, bucket):
    return lambda r: combined_baseline(r) and not bucket_match(r, factor, bucket)


def view_delta(view, which='dynamic'):
    return view[which]['comparison'].get('mean_delta_pct')


def passes_lane(view, min_delta=0.0):
    d = view_delta(view, 'dynamic')
    f = view_delta(view, 'fixed_anchor')
    return bool(
        d is not None and f is not None
        and d > min_delta and f > min_delta
        and view['agreement']['mean_direction_agrees']
    )


def no_short_harm(view, tolerance=-0.10):
    d = view_delta(view, 'dynamic')
    f = view_delta(view, 'fixed_anchor')
    return bool(d is not None and f is not None and d >= tolerance and f >= tolerance)


def evaluate_candidate(rows_by_lane, factor, bucket, principal_h):
    pred = candidate_pred(factor, bucket)
    evals = {
        lane: {f'{h}h': paired.evaluate_lane(rows, combined_baseline, pred, h) for h in base.HORIZONS}
        for lane, rows in rows_by_lane.items()
    }
    principal_full = evals['full'][f'{principal_h}h']
    principal_train = evals['train'][f'{principal_h}h']
    principal_hold = evals['holdout'][f'{principal_h}h']
    hold3 = evals['holdout']['3h']

    baseline_n = principal_hold['baseline'].get('n', 0)
    veto_n = principal_hold['fixed_anchor']['vetoed_baseline_anchors'].get('n', 0)
    enough = baseline_n >= 6 and veto_n >= 2
    passed = bool(
        enough
        and passes_lane(principal_full)
        and passes_lane(principal_train)
        and passes_lane(principal_hold)
        and no_short_harm(hold3)
    )
    return {
        'factor': factor,
        'bucket': bucket,
        'principal_horizon_h': principal_h,
        'enough_evidence': enough,
        'paired_gate_passed': passed,
        'summary': {
            'full_dynamic_delta_pct': view_delta(principal_full,'dynamic'),
            'full_fixed_delta_pct': view_delta(principal_full,'fixed_anchor'),
            'train_dynamic_delta_pct': view_delta(principal_train,'dynamic'),
            'train_fixed_delta_pct': view_delta(principal_train,'fixed_anchor'),
            'holdout_dynamic_delta_pct': view_delta(principal_hold,'dynamic'),
            'holdout_fixed_delta_pct': view_delta(principal_hold,'fixed_anchor'),
            'holdout_3h_dynamic_delta_pct': view_delta(hold3,'dynamic'),
            'holdout_3h_fixed_delta_pct': view_delta(hold3,'fixed_anchor'),
            'holdout_vetoed_anchor_n': veto_n,
            'holdout_replacement_n': principal_hold['agreement']['replacement_episode_count'],
        },
        'lanes': evals,
    }


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train, holdout, cutoff = paired.split_60_40(hourly)
    lanes = {'full': hourly, 'train': train, 'holdout': holdout}

    autopsy = residual.run(path)
    source = [x for x in autopsy.get('stable_harmful_buckets', []) if x.get('factor') in ELIGIBLE_FACTORS]
    # De-duplicate the same factor/bucket/horizon if the autopsy ever repeats it.
    seen, candidates = set(), []
    for item in source:
        key = (item['factor'], item['bucket'], int(item['horizon_h']))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(evaluate_candidate(lanes, *key))

    candidates.sort(key=lambda x: (
        not x['paired_gate_passed'],
        -((x['summary'].get('holdout_dynamic_delta_pct') or -999) + (x['summary'].get('holdout_fixed_delta_pct') or -999)),
    ))
    passed = [c for c in candidates if c['paired_gate_passed']]
    decision = 'ONE_OR_MORE_PAIRED_THIRD_CANDIDATES_FOUND' if passed else 'NO_THIRD_CANDIDATE_PASSES_PAIRED_GATE'

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'coverage': {'snapshots':len(snaps),'hourly_v6_rows':len(hourly),'cutoff_at':cutoff.isoformat() if cutoff else None,'source_stable_harmful_buckets':len(source),'excluded':excluded},
        'candidate_count': len(candidates),
        'passed_candidate_count': len(passed),
        'passed_candidates': [{k:v for k,v in c.items() if k != 'lanes'} for c in passed],
        'ranked_candidates': candidates,
        'research_decision': decision,
        'next_decision': 'Advance at most ONE highest-ranked passed candidate to a separate prospective shadow. If none pass, stop adding filters and investigate model features/regime representation instead.',
        'production_change_recommended': False,
        'guardrails': {'research_only':True,'production_threshold':base.THRESHOLD,'production_threshold_changed':False,'production_scoring_changed':False,'auto_promotion_enabled':False,'can_override_production':False,'live_execution':False},
    }


def main():
    r=run()
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({
        'schema':r['schema'],'coverage':r['coverage'],'candidate_count':r['candidate_count'],
        'passed_candidate_count':r['passed_candidate_count'],'passed_candidates':r['passed_candidates'],
        'top_ranked':[{k:v for k,v in c.items() if k!='lanes'} for c in r['ranked_candidates'][:6]],
        'research_decision':r['research_decision'],'guardrails':r['guardrails'],
    },sort_keys=True))

if __name__=='__main__':
    main()
