#!/usr/bin/env python3
"""Paired revalidation of ATLAS accepted research shadows.

Rechecks two previously advanced research candidates under both dynamic and
fixed-anchor episode evaluation:
A) V6 baseline -> fourth-vote demotion
B) fourth-vote baseline -> LONG+CLOSE structure veto

A candidate remains trusted for prospective research only when the principal
horizon improves in full AND holdout in both views, with no sign reversal.
No Production changes are made.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as fourth
import long_close_structure_veto_shadow as lc
import counterfactual_episode_evaluation as paired

OUT = Path('status/accepted-shadow-paired-revalidation.json')
SCHEMA = 'ATLAS_ACCEPTED_SHADOW_PAIRED_REVALIDATION_V1'


def v6_baseline(r):
    return r['corrected_score'] >= base.THRESHOLD


def fourth_candidate(r):
    return fourth.candidate_score(r) >= base.THRESHOLD


def long_close_candidate(r):
    return lc.candidate_qualified(r)


def eval_candidate(rows_by_lane, baseline_pred, candidate_pred):
    out = {}
    for lane, rows in rows_by_lane.items():
        out[lane] = {f'{h}h': paired.evaluate_lane(rows, baseline_pred, candidate_pred, h) for h in base.HORIZONS}
    return out


def positive_both(view):
    d = view['dynamic']['comparison'].get('mean_delta_pct')
    f = view['fixed_anchor']['comparison'].get('mean_delta_pct')
    return d is not None and f is not None and d > 0 and f > 0 and view['agreement']['mean_direction_agrees']


def no_material_short_harm(view, tolerance=-0.10):
    d = view['dynamic']['comparison'].get('mean_delta_pct')
    f = view['fixed_anchor']['comparison'].get('mean_delta_pct')
    return d is not None and f is not None and d >= tolerance and f >= tolerance


def assess(name, result, principal_h):
    full = result['full'][f'{principal_h}h']
    hold = result['holdout'][f'{principal_h}h']
    train = result['train'][f'{principal_h}h']
    h3_hold = result['holdout']['3h']
    principal_ok = positive_both(full) and positive_both(train) and positive_both(hold)
    short_ok = no_material_short_harm(h3_hold)
    trusted = bool(principal_ok and short_ok)
    return {
        'candidate': name,
        'principal_horizon_h': principal_h,
        'principal_full_positive_in_dynamic_and_fixed': positive_both(full),
        'principal_train_positive_in_dynamic_and_fixed': positive_both(train),
        'principal_holdout_positive_in_dynamic_and_fixed': positive_both(hold),
        'holdout_3h_not_materially_harmed_in_both_views': short_ok,
        'paired_revalidation_passed': trusted,
        'research_status': 'KEEP_PROSPECTIVE_RESEARCH_CANDIDATE' if trusted else 'DOWNGRADE_PENDING_METHODOLOGY_REVIEW',
    }


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train, holdout, cutoff = paired.split_60_40(hourly)
    lanes = {'full': hourly, 'train': train, 'holdout': holdout}

    fourth_res = eval_candidate(lanes, v6_baseline, fourth_candidate)
    long_close_res = eval_candidate(lanes, fourth_candidate, long_close_candidate)
    fourth_assess = assess('FOURTH_VOTE_DEMOTION', fourth_res, 12)
    long_close_assess = assess('LONG_CLOSE_STRUCTURE_VETO', long_close_res, 12)

    all_pass = fourth_assess['paired_revalidation_passed'] and long_close_assess['paired_revalidation_passed']
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'coverage': {'snapshots': len(snaps), 'hourly_v6_rows': len(hourly), 'cutoff_at': cutoff.isoformat() if cutoff else None, 'excluded': excluded},
        'method': {
            'dynamic_sequence': 'candidate qualification is applied before horizon de-correlation; later replacement episodes are allowed',
            'fixed_anchor': 'baseline independent episode anchors are frozen; candidate can only remove anchors and cannot introduce replacements',
            'promotion_rule': 'principal 12h mean delta must be >0 in full/train/holdout in BOTH views; holdout 3h may not degrade by more than 0.10pp in either view',
        },
        'fourth_vote': {'assessment': fourth_assess, 'lanes': fourth_res},
        'long_close': {'assessment': long_close_assess, 'lanes': long_close_res},
        'research_decision': 'BOTH_ACCEPTED_SHADOWS_SURVIVE_PAIRED_REVALIDATION' if all_pass else 'ONE_OR_MORE_ACCEPTED_SHADOWS_REQUIRE_DOWNGRADE',
        'production_change_recommended': False,
        'guardrails': {'research_only': True, 'production_threshold': base.THRESHOLD, 'production_threshold_changed': False, 'production_scoring_changed': False, 'auto_promotion_enabled': False, 'can_override_production': False, 'live_execution': False},
    }


def main():
    r = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': r['schema'], 'coverage': r['coverage'],
        'fourth_vote_assessment': r['fourth_vote']['assessment'],
        'long_close_assessment': r['long_close']['assessment'],
        'research_decision': r['research_decision'], 'guardrails': r['guardrails'],
    }, sort_keys=True))

if __name__ == '__main__':
    main()
