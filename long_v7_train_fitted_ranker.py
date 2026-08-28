#!/usr/bin/env python3
"""ATLAS LONG V7 Candidate B: train-fitted component ranker.

This is the first LONG V7 candidate whose weights are learned ONLY from the
chronological training segment and then frozen before holdout evaluation.
It uses existing V6 component attribution only; no new market data, threshold
search, or hyper-parameter sweep is performed.

Method
------
1. Build settled independent 12h LONG episodes (maturity before independence).
2. Split chronologically 60/40 using the existing ATLAS split helper.
3. On TRAIN only, compute Spearman correlation of each primitive V6 component
   with 12h LONG return.
4. Freeze those correlations as weights. Standardize each component using TRAIN
   mean/std and form a linear quality score = sum(weight * train-zscore).
5. Compare equal-coverage top-K against V6 in TRAIN, HOLDOUT, and FULL, where K
   is the number of V6 episodes with corrected_score >= 68 in that lane.
6. Leave-one-symbol-out refits weights on TRAIN excluding each symbol and tests
   HOLDOUT excluding that symbol.

The candidate advances only if holdout mean improves, train does not degrade,
and all eligible LOO holdout tests are non-worse. Research-only; Production is
untouched.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import counterfactual_episode_evaluation as paired
import v6_long_representation_audit as audit

OUT = Path('status/long-v7-train-fitted-ranker.json')
SCHEMA = 'ATLAS_LONG_V7_TRAIN_FITTED_RANKER_V1'
H = 12
FEATURES = (
    'trend_base',
    'volume_bonus',
    'rs_adjustment',
    'futures_adjustment',
    'obstacle_adjustment',
    'direction_votes',
)


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _episode_pool(rows):
    settled = [r for r in rows if r.get('direction') == 'LONG' and r.get('return_12h_pct') is not None]
    return base.independent(settled, H)


def _stats(values):
    if not values:
        return 0.0, 1.0
    mu = sum(values) / len(values)
    var = sum((x - mu) ** 2 for x in values) / len(values)
    sd = math.sqrt(var)
    return mu, sd if sd > 1e-12 else 1.0


def fit(train_pool):
    params = {}
    for f in FEATURES:
        vals = [_num(r.get(f)) for r in train_pool]
        rets = [_num(r.get('return_12h_pct')) for r in train_pool]
        mu, sd = _stats(vals)
        rho = audit.spearman(vals, rets)
        params[f] = {
            'mean': mu,
            'std': sd,
            'weight': 0.0 if rho is None else float(rho),
        }
    return params


def quality(row, params):
    total = 0.0
    for f in FEATURES:
        p = params[f]
        z = (_num(row.get(f)) - p['mean']) / p['std']
        total += p['weight'] * z
    return total


def _k(pool):
    return sum(1 for r in pool if _num(r.get('corrected_score')) >= base.THRESHOLD)


def _rank_v6(pool):
    return sorted(pool, key=lambda r: (-_num(r.get('corrected_score')), str(r.get('captured_at')), str(r.get('symbol'))))


def _rank_v7(pool, params):
    return sorted(pool, key=lambda r: (-quality(r, params), str(r.get('captured_at')), str(r.get('symbol'))))


def evaluate(pool, params):
    k = _k(pool)
    b = _rank_v6(pool)[:k]
    c = _rank_v7(pool, params)[:k]
    bs = base.stats(b, H)
    cs = base.stats(c, H)
    if bs['n'] != k or cs['n'] != k:
        raise AssertionError('mature equal-coverage invariant violated')
    return {
        'pool_n': len(pool),
        'equal_mature_coverage_k': k,
        'baseline_v6': bs,
        'candidate_v7': cs,
        'comparison': {
            'mean_delta_pct': None if bs['mean_pct'] is None or cs['mean_pct'] is None else round(cs['mean_pct'] - bs['mean_pct'], 4),
            'win_rate_delta_pct': None if bs['win_rate_pct'] is None or cs['win_rate_pct'] is None else round(cs['win_rate_pct'] - bs['win_rate_pct'], 2),
        },
    }


def loo(train_rows, holdout_rows):
    symbols = sorted({r.get('symbol') for r in _episode_pool(train_rows + holdout_rows) if r.get('symbol')})
    tests = []
    for sym in symbols:
        tr = _episode_pool([r for r in train_rows if r.get('symbol') != sym])
        ho = _episode_pool([r for r in holdout_rows if r.get('symbol') != sym])
        if len(tr) < 5:
            continue
        params = fit(tr)
        ev = evaluate(ho, params)
        tests.append({
            'left_out_symbol': sym,
            'train_n': len(tr),
            'holdout_pool_n': ev['pool_n'],
            'k': ev['equal_mature_coverage_k'],
            'mean_delta_pct': ev['comparison']['mean_delta_pct'],
            'win_rate_delta_pct': ev['comparison']['win_rate_delta_pct'],
        })
    eligible = [x for x in tests if x['k'] >= 2 and x['mean_delta_pct'] is not None]
    return {
        'tests': tests,
        'eligible_test_count': len(eligible),
        'non_worse_count': sum(1 for x in eligible if x['mean_delta_pct'] >= 0),
        'positive_count': sum(1 for x in eligible if x['mean_delta_pct'] > 0),
        'all_holdout_mean_non_worse': bool(eligible) and all(x['mean_delta_pct'] >= 0 for x in eligible),
    }


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train_rows, holdout_rows, cutoff = paired.split_60_40(hourly)

    train_pool = _episode_pool(train_rows)
    holdout_pool = _episode_pool(holdout_rows)
    full_pool = _episode_pool(hourly)
    params = fit(train_pool)

    lanes = {
        'train': evaluate(train_pool, params),
        'holdout': evaluate(holdout_pool, params),
        'full_descriptive': evaluate(full_pool, params),
    }
    cross = loo(train_rows, holdout_rows)

    tdelta = lanes['train']['comparison']['mean_delta_pct']
    hdelta = lanes['holdout']['comparison']['mean_delta_pct']
    enough = lanes['train']['equal_mature_coverage_k'] >= 3 and lanes['holdout']['equal_mature_coverage_k'] >= 3
    pass_gate = (
        enough
        and tdelta is not None and tdelta >= 0
        and hdelta is not None and hdelta > 0
        and cross['all_holdout_mean_non_worse']
    )

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'A train-fitted combination of primitive V6 components ranks 12h LONG quality better than total V6 score at equal mature coverage.',
        'coverage': {
            'snapshots': len(snaps),
            'hourly_v6_rows': len(hourly),
            'cutoff_at': cutoff.isoformat() if cutoff else None,
            'train_long_episode_n': len(train_pool),
            'holdout_long_episode_n': len(holdout_pool),
            'excluded': excluded,
        },
        'fit': {
            'fit_scope': 'TRAIN_ONLY',
            'features': list(FEATURES),
            'parameters': params,
            'no_threshold_search': True,
            'no_hyperparameter_sweep': True,
        },
        'lanes': lanes,
        'leave_one_symbol_out': cross,
        'gate': {
            'minimum_train_and_holdout_k': 3,
            'train_mean_delta_non_worse': True,
            'holdout_mean_delta_positive': True,
            'all_eligible_loo_holdout_mean_non_worse': True,
            'enough_evidence': enough,
            'passed': pass_gate,
        },
        'research_decision': 'ADVANCE_LONG_V7_TRAIN_FITTED_TO_PAIRED_REPLAY' if pass_gate else 'REJECT_LONG_V7_TRAIN_FITTED_RANKER',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True,
            'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False,
            'production_scoring_changed': False,
            'auto_promotion_enabled': False,
            'can_override_production': False,
            'live_execution': False,
        },
    }


def main():
    out = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'coverage': out['coverage'],
        'fit': out['fit'],
        'lanes': out['lanes'],
        'leave_one_symbol_out': out['leave_one_symbol_out'],
        'gate': out['gate'],
        'research_decision': out['research_decision'],
        'guardrails': out['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
