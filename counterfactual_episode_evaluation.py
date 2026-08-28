#!/usr/bin/env python3
"""Reusable paired counterfactual episode evaluation for ATLAS research.

Two views are intentionally reported:
1) dynamic sequence: re-run independence AFTER applying the candidate; this
   reflects which later opportunities would actually become eligible.
2) fixed anchor: keep the baseline independent episode anchors and remove only
   anchors rejected by the candidate; this isolates the causal quality of the
   rule without contamination from replacement episodes.

Research-only helper. It never mutates Production.
"""
from __future__ import annotations

import qualified_false_confidence_audit as base


def episode_id(r):
    return f"{r['symbol']}|{r['direction']}|{r['captured_at'].isoformat()}"


def delta(a, b):
    return {
        'mean_delta_pct': None if a.get('mean_pct') is None or b.get('mean_pct') is None else round(b['mean_pct'] - a['mean_pct'], 4),
        'win_rate_delta_pct': None if a.get('win_rate_pct') is None or b.get('win_rate_pct') is None else round(b['win_rate_pct'] - a['win_rate_pct'], 2),
        'n_delta': int(b.get('n', 0)) - int(a.get('n', 0)),
    }


def evaluate_lane(rows, baseline_pred, candidate_pred, horizon_h):
    baseline_pool = [r for r in rows if baseline_pred(r)]
    candidate_pool = [r for r in rows if candidate_pred(r)]
    baseline_eps = base.independent(baseline_pool, horizon_h)
    dynamic_eps = base.independent(candidate_pool, horizon_h)

    bmap = {episode_id(r): r for r in baseline_eps}
    cmap = {episode_id(r): r for r in dynamic_eps}
    retained = [r for k, r in bmap.items() if k in cmap]
    removed_dynamic = [r for k, r in bmap.items() if k not in cmap]
    replacements = [r for k, r in cmap.items() if k not in bmap]

    fixed_candidate = [r for r in baseline_eps if candidate_pred(r)]
    fixed_vetoed = [r for r in baseline_eps if not candidate_pred(r)]

    bstats = base.stats(baseline_eps, horizon_h)
    dstats = base.stats(dynamic_eps, horizon_h)
    fstats = base.stats(fixed_candidate, horizon_h)
    vstats = base.stats(fixed_vetoed, horizon_h)
    rstats = base.stats(replacements, horizon_h)

    return {
        'horizon_h': horizon_h,
        'pool_hours': {'baseline': len(baseline_pool), 'candidate': len(candidate_pool)},
        'baseline': bstats,
        'dynamic': {
            'candidate': dstats,
            'comparison': delta(bstats, dstats),
            'retained': base.stats(retained, horizon_h),
            'removed_from_baseline_set': base.stats(removed_dynamic, horizon_h),
            'replacement_episodes': rstats,
            'counts': {
                'baseline_episodes': len(baseline_eps), 'candidate_episodes': len(dynamic_eps),
                'retained': len(retained), 'removed': len(removed_dynamic), 'replacements': len(replacements),
            },
        },
        'fixed_anchor': {
            'candidate': fstats,
            'comparison': delta(bstats, fstats),
            'vetoed_baseline_anchors': vstats,
            'counts': {'baseline_episodes': len(baseline_eps), 'candidate_episodes': len(fixed_candidate), 'vetoed': len(fixed_vetoed)},
        },
        'agreement': {
            'mean_direction_agrees': (
                delta(bstats, dstats)['mean_delta_pct'] is not None
                and delta(bstats, fstats)['mean_delta_pct'] is not None
                and ((delta(bstats, dstats)['mean_delta_pct'] >= 0) == (delta(bstats, fstats)['mean_delta_pct'] >= 0))
            ),
            'replacement_episode_count': len(replacements),
            'replacement_mean_pct': rstats.get('mean_pct'),
        },
    }


def split_60_40(rows):
    rows = sorted(rows, key=lambda r: r['captured_at'])
    hours = sorted({r['captured_at'].replace(minute=0, second=0, microsecond=0) for r in rows})
    if len(hours) < 2:
        return rows, [], None
    idx = max(1, min(len(hours) - 1, int(len(hours) * 0.60)))
    cutoff = hours[idx]
    return [r for r in rows if r['captured_at'] < cutoff], [r for r in rows if r['captured_at'] >= cutoff], cutoff
