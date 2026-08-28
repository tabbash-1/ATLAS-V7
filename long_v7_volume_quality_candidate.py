#!/usr/bin/env python3
"""ATLAS LONG V7 Candidate A: volume-quality ranking at equal coverage.

Purpose
-------
The full V6 LONG representation audit found that `volume_bonus` is the only
numeric component with stable positive 12h discrimination across train,
holdout, and leave-one-symbol-out, while the total V6 score is not positively
discriminative.

This candidate deliberately avoids choosing a new threshold. On a fixed set of
independent LONG episodes it compares:

* V6 baseline ranking: corrected_score descending
* Candidate ranking: volume_bonus descending

For each lane the candidate selects exactly the same number of episodes as V6
would qualify at score >= 68. This isolates ranking quality from opportunity
count. Ties are resolved only by timestamp/symbol for determinism, not by V6
score.

Research-only. No Production score, threshold, execution, or shadow endpoint is
changed by this module.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import counterfactual_episode_evaluation as paired
import v6_long_representation_audit as audit

OUT = Path('status/long-v7-volume-quality-candidate.json')
SCHEMA = 'ATLAS_LONG_V7_VOLUME_QUALITY_CANDIDATE_V1'
H = 12


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _iso(v):
    return v.isoformat() if hasattr(v, 'isoformat') else (str(v) if v is not None else None)


def _episode_pool(rows):
    # Fixed anchors first; both baseline and candidate are evaluated on the exact
    # same independent episode set to prevent episode-substitution contamination.
    return audit.episodes(rows)


def _k_from_v6(pool):
    return sum(1 for r in pool if _num(r.get('corrected_score')) >= base.THRESHOLD)


def _rank_v6(pool):
    return sorted(
        pool,
        key=lambda r: (-_num(r.get('corrected_score')), str(r.get('captured_at') or ''), str(r.get('symbol') or '')),
    )


def _rank_candidate(pool):
    return sorted(
        pool,
        key=lambda r: (-_num(r.get('volume_bonus')), str(r.get('captured_at') or ''), str(r.get('symbol') or '')),
    )


def _select(pool, ranker):
    k = _k_from_v6(pool)
    return ranker(pool)[:k], k


def lane(rows):
    pool = _episode_pool(rows)
    baseline, k = _select(pool, _rank_v6)
    candidate, _ = _select(pool, _rank_candidate)
    bs = base.stats(baseline, H)
    cs = base.stats(candidate, H)
    bkeys = {(r.get('symbol'), _iso(r.get('captured_at'))) for r in baseline}
    ckeys = {(r.get('symbol'), _iso(r.get('captured_at'))) for r in candidate}
    return {
        'independent_long_episode_pool': len(pool),
        'equal_coverage_k': k,
        'baseline_v6_topk': bs,
        'candidate_volume_topk': cs,
        'comparison': {
            'mean_delta_pct': None if bs['mean_pct'] is None or cs['mean_pct'] is None else round(cs['mean_pct'] - bs['mean_pct'], 4),
            'win_rate_delta_pct': None if bs['win_rate_pct'] is None or cs['win_rate_pct'] is None else round(cs['win_rate_pct'] - bs['win_rate_pct'], 2),
            'overlap_n': len(bkeys & ckeys),
            'replaced_n': len(bkeys - ckeys),
            'added_n': len(ckeys - bkeys),
        },
        'baseline_members': [
            {'symbol': r.get('symbol'), 'captured_at': _iso(r.get('captured_at')), 'score': r.get('corrected_score'), 'volume_bonus': r.get('volume_bonus'), 'return_12h_pct': r.get('return_12h_pct')}
            for r in baseline
        ],
        'candidate_members': [
            {'symbol': r.get('symbol'), 'captured_at': _iso(r.get('captured_at')), 'score': r.get('corrected_score'), 'volume_bonus': r.get('volume_bonus'), 'return_12h_pct': r.get('return_12h_pct')}
            for r in candidate
        ],
    }


def leave_one_symbol_out(rows):
    pool = _episode_pool(rows)
    syms = sorted({r.get('symbol') for r in pool if r.get('symbol')})
    tests = []
    for sym in syms:
        subset = [r for r in rows if r.get('symbol') != sym]
        x = lane(subset)
        tests.append({
            'left_out_symbol': sym,
            'pool_n': x['independent_long_episode_pool'],
            'k': x['equal_coverage_k'],
            'mean_delta_pct': x['comparison']['mean_delta_pct'],
            'win_rate_delta_pct': x['comparison']['win_rate_delta_pct'],
        })
    finite = [x for x in tests if x['mean_delta_pct'] is not None and x['k'] >= 2]
    return {
        'tests': tests,
        'all_mean_non_worse': bool(finite) and all(x['mean_delta_pct'] >= 0 for x in finite),
        'all_mean_positive': bool(finite) and all(x['mean_delta_pct'] > 0 for x in finite),
        'positive_test_count': sum(1 for x in finite if x['mean_delta_pct'] > 0),
        'eligible_test_count': len(finite),
    }


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train_rows, holdout_rows, cutoff = paired.split_60_40(hourly)

    lanes = {
        'full': lane(hourly),
        'train': lane(train_rows),
        'holdout': lane(holdout_rows),
    }
    loo = leave_one_symbol_out(hourly)

    def positive(name):
        d = lanes[name]['comparison']['mean_delta_pct']
        return d is not None and d > 0

    enough = lanes['train']['equal_coverage_k'] >= 3 and lanes['holdout']['equal_coverage_k'] >= 3
    advance = enough and positive('train') and positive('holdout') and positive('full') and loo['all_mean_non_worse']

    decision = 'ADVANCE_LONG_V7_VOLUME_RANKING_TO_PAIRED_REPLAY' if advance else 'REJECT_LONG_V7_VOLUME_RANKING'
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'At equal opportunity count, ranking LONG by the only stable positive V6 component (volume_bonus) selects better 12h episodes than ranking by total V6 score.',
        'coverage': {
            'snapshots': len(snaps),
            'hourly_v6_rows': len(hourly),
            'cutoff_at': cutoff.isoformat() if cutoff else None,
            'excluded': excluded,
        },
        'lanes': lanes,
        'leave_one_symbol_out': loo,
        'gate': {
            'equal_coverage_required': True,
            'train_mean_delta_must_be_positive': True,
            'holdout_mean_delta_must_be_positive': True,
            'full_mean_delta_must_be_positive': True,
            'loo_mean_must_be_non_worse_in_all_eligible_tests': True,
            'minimum_train_and_holdout_k': 3,
            'enough_evidence': enough,
            'passed': advance,
        },
        'research_decision': decision,
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
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': result['schema'],
        'coverage': result['coverage'],
        'lanes': {k: {'equal_coverage_k': v['equal_coverage_k'], 'baseline': v['baseline_v6_topk'], 'candidate': v['candidate_volume_topk'], 'comparison': v['comparison']} for k, v in result['lanes'].items()},
        'leave_one_symbol_out': result['leave_one_symbol_out'],
        'gate': result['gate'],
        'research_decision': result['research_decision'],
        'guardrails': result['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
