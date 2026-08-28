#!/usr/bin/env python3
"""ATLAS LONG V7 Candidate R1: 24h anti-chase ranking.

The raw representation audit found `momentum_24h_pct` to be the only raw feature
with stable negative 12h discrimination across Train, Holdout and every
leave-one-symbol-out test. This candidate tests that finding without changing
opportunity count: at equal mature coverage K, V6 ranks by total score while R1
ranks LONG by LOWER 24h momentum first.

No new threshold is selected and no Production code is changed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import counterfactual_episode_evaluation as paired
import long_v7_raw_representation_audit as raw

OUT = Path('status/long-v7-anti-chase-candidate.json')
SCHEMA = 'ATLAS_LONG_V7_ANTI_CHASE_CANDIDATE_R1'
H = 12


def _num(v, default=0.0):
    return base.fnum(v, default)


def pool(rows):
    return raw.mature_episodes(rows)


def k_v6(eps):
    return sum(1 for r in eps if _num(r.get('corrected_score')) >= base.THRESHOLD)


def evaluate(rows):
    eps = pool(rows)
    k = k_v6(eps)
    baseline = sorted(eps, key=lambda r: (-_num(r.get('corrected_score')), str(r.get('captured_at')), str(r.get('symbol'))))[:k]
    candidate = sorted(eps, key=lambda r: (_num(r.get('momentum_24h_pct')), str(r.get('captured_at')), str(r.get('symbol'))))[:k]
    bs = base.stats(baseline, H)
    cs = base.stats(candidate, H)
    if bs['n'] != k or cs['n'] != k:
        raise AssertionError('equal mature coverage violated')
    return {
        'pool_n': len(eps),
        'equal_mature_coverage_k': k,
        'baseline_v6': bs,
        'candidate_anti_chase': cs,
        'comparison': {
            'mean_delta_pct': None if bs['mean_pct'] is None or cs['mean_pct'] is None else round(cs['mean_pct'] - bs['mean_pct'], 4),
            'win_rate_delta_pct': None if bs['win_rate_pct'] is None or cs['win_rate_pct'] is None else round(cs['win_rate_pct'] - bs['win_rate_pct'], 2),
        },
    }


def loo(rows):
    eps = pool(rows)
    syms = sorted({r.get('symbol') for r in eps if r.get('symbol')})
    tests = []
    for sym in syms:
        ev = evaluate([r for r in rows if r.get('symbol') != sym])
        tests.append({
            'left_out_symbol': sym,
            'k': ev['equal_mature_coverage_k'],
            'mean_delta_pct': ev['comparison']['mean_delta_pct'],
            'win_rate_delta_pct': ev['comparison']['win_rate_delta_pct'],
        })
    eligible = [x for x in tests if x['k'] >= 2 and x['mean_delta_pct'] is not None]
    return {
        'tests': tests,
        'eligible_tests': len(eligible),
        'positive_tests': sum(1 for x in eligible if x['mean_delta_pct'] > 0),
        'non_worse_tests': sum(1 for x in eligible if x['mean_delta_pct'] >= 0),
        'all_mean_non_worse': bool(eligible) and all(x['mean_delta_pct'] >= 0 for x in eligible),
    }


def run(path=base.SRC):
    snaps, hourly = raw.load_rows(path)
    train_rows, holdout_rows, cutoff = paired.split_60_40(hourly)
    lanes = {'full': evaluate(hourly), 'train': evaluate(train_rows), 'holdout': evaluate(holdout_rows)}
    cross = loo(hourly)
    enough = lanes['train']['equal_mature_coverage_k'] >= 3 and lanes['holdout']['equal_mature_coverage_k'] >= 3
    deltas = {k: v['comparison']['mean_delta_pct'] for k, v in lanes.items()}
    passed = enough and all(deltas[x] is not None and deltas[x] > 0 for x in ('full','train','holdout')) and cross['all_mean_non_worse']
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'For 12h LONG selection, avoiding already-extended 24h momentum ranks opportunities better than total V6 score at identical mature coverage.',
        'coverage': {'snapshots': len(snaps), 'cutoff_at': cutoff.isoformat() if cutoff else None},
        'lanes': lanes,
        'leave_one_symbol_out': cross,
        'gate': {
            'equal_mature_coverage_required': True,
            'full_train_holdout_mean_delta_positive': True,
            'all_loo_mean_non_worse': True,
            'minimum_train_holdout_k': 3,
            'enough_evidence': enough,
            'passed': passed,
        },
        'research_decision': 'ADVANCE_LONG_V7_ANTI_CHASE_TO_PAIRED_REPLAY' if passed else 'REJECT_LONG_V7_ANTI_CHASE',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True,
            'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False,
            'production_scoring_changed': False,
            'can_override_production': False,
            'auto_promotion_enabled': False,
            'live_execution': False,
        },
    }


def main():
    out = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    main()
