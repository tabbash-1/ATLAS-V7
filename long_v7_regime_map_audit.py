#!/usr/bin/env python3
"""ATLAS LONG V7 regime-map audit (fixed-episode V2).

Global monotonic LONG rankers failed out of sample. This audit therefore tests
pre-registered market-state buckets using raw historical features already stored
in Production snapshots. It does NOT optimize cut points on outcomes.

Method correction in V2: mature independent 12h LONG episodes are built ONCE on
the full history, then those fixed episodes are split chronologically 60/40.
This guarantees Train + Holdout == Full and prevents boundary re-anchoring.

Natural trading bins:
- 24h momentum: <=0, 0-1, 1-2, 2-4, >4 %
- RSI14: <55, 55-62, 62-68, 68-72, >72
- price extension vs EMA20 in ATR: <0, 0-0.5, 0.5-1, 1-1.5, >1.5 ATR
- paced RV: <0.7, 0.7-1, 1-1.5, 1.5-2.5, >=2.5

A bucket is called stable helpful/harmful only when Train and Holdout have at
least 2 fixed mature independent 12h episodes each and both means share the
sign. Pairwise regimes are limited to Momentum×RSI and Momentum×Extension to
avoid a combinatorial search.

Research-only; Production is untouched.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_v7_raw_representation_audit as raw
import long_v7_fixed_episode_split as fixed

OUT = Path('status/long-v7-regime-map-audit.json')
SCHEMA = 'ATLAS_LONG_V7_REGIME_MAP_AUDIT_V2_FIXED_EPISODES'
H = 12
MIN_LANE_N = 2


def bucket_momentum(v):
    v = float(v)
    if v <= 0: return '<=0'
    if v <= 1: return '0_1'
    if v <= 2: return '1_2'
    if v <= 4: return '2_4'
    return '>4'


def bucket_rsi(v):
    v = float(v)
    if v < 55: return '<55'
    if v < 62: return '55_62'
    if v < 68: return '62_68'
    if v < 72: return '68_72'
    return '>=72'


def bucket_extension(v):
    v = float(v)
    if v < 0: return '<0'
    if v < 0.5: return '0_0.5'
    if v < 1.0: return '0.5_1'
    if v < 1.5: return '1_1.5'
    return '>=1.5'


def bucket_rv(v):
    v = float(v)
    if v < 0.7: return '<0.7'
    if v < 1.0: return '0.7_1'
    if v < 1.5: return '1_1.5'
    if v < 2.5: return '1.5_2.5'
    return '>=2.5'

BUCKETERS = {
    'momentum': ('momentum_24h_pct', bucket_momentum),
    'rsi': ('rsi14', bucket_rsi),
    'extension': ('price_extension_atr', bucket_extension),
    'rv': ('paced_relative_volume', bucket_rv),
}


def summarize(rows):
    return base.stats(rows, H)


def group_single(eps, feature_name):
    field, fn = BUCKETERS[feature_name]
    groups = defaultdict(list)
    for r in eps:
        v = r.get(field)
        if v is None:
            continue
        groups[fn(v)].append(r)
    return {k: summarize(v) for k, v in sorted(groups.items())}


def group_pair(eps, a, b):
    fa, fna = BUCKETERS[a]
    fb, fnb = BUCKETERS[b]
    groups = defaultdict(list)
    for r in eps:
        va, vb = r.get(fa), r.get(fb)
        if va is None or vb is None:
            continue
        groups[f'{fna(va)}|{fnb(vb)}'].append(r)
    return {k: summarize(v) for k, v in sorted(groups.items())}


def stable_compare(train_map, holdout_map):
    helpful, harmful = [], []
    keys = sorted(set(train_map) & set(holdout_map))
    for k in keys:
        tr, ho = train_map[k], holdout_map[k]
        if tr.get('n', 0) < MIN_LANE_N or ho.get('n', 0) < MIN_LANE_N:
            continue
        tm, hm = tr.get('mean_pct'), ho.get('mean_pct')
        if tm is None or hm is None:
            continue
        row = {'bucket': k, 'train': tr, 'holdout': ho}
        if tm > 0 and hm > 0:
            helpful.append(row)
        elif tm < 0 and hm < 0:
            harmful.append(row)
    helpful.sort(key=lambda x: min(x['train']['mean_pct'], x['holdout']['mean_pct']), reverse=True)
    harmful.sort(key=lambda x: max(x['train']['mean_pct'], x['holdout']['mean_pct']))
    return helpful, harmful


def run(path=base.SRC):
    snaps, hourly = raw.load_rows(path)
    full_eps = fixed.full_fixed_episodes(hourly)
    train_eps, holdout_eps, cutoff = fixed.split_fixed_60_40(full_eps)
    if len(train_eps) + len(holdout_eps) != len(full_eps):
        raise AssertionError('fixed episode split count invariant violated')

    singles = {}
    stable_helpful, stable_harmful = [], []
    for name in BUCKETERS:
        tr = group_single(train_eps, name)
        ho = group_single(holdout_eps, name)
        fu = group_single(full_eps, name)
        hp, hm = stable_compare(tr, ho)
        singles[name] = {'full': fu, 'train': tr, 'holdout': ho, 'stable_helpful': hp, 'stable_harmful': hm}
        stable_helpful += [{'regime': name, **x} for x in hp]
        stable_harmful += [{'regime': name, **x} for x in hm]

    pairs = {}
    for a, b in [('momentum', 'rsi'), ('momentum', 'extension')]:
        key = f'{a}_x_{b}'
        tr = group_pair(train_eps, a, b)
        ho = group_pair(holdout_eps, a, b)
        fu = group_pair(full_eps, a, b)
        hp, hm = stable_compare(tr, ho)
        pairs[key] = {'full': fu, 'train': tr, 'holdout': ho, 'stable_helpful': hp, 'stable_harmful': hm}
        stable_helpful += [{'regime': key, **x} for x in hp]
        stable_harmful += [{'regime': key, **x} for x in hm]

    stable_helpful.sort(key=lambda x: min(x['train']['mean_pct'], x['holdout']['mean_pct']), reverse=True)
    stable_harmful.sort(key=lambda x: max(x['train']['mean_pct'], x['holdout']['mean_pct']))

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'coverage': {
            'snapshots': len(snaps),
            'cutoff_at': cutoff.isoformat() if hasattr(cutoff, 'isoformat') else (str(cutoff) if cutoff else None),
            'full_episode_n': len(full_eps),
            'train_episode_n': len(train_eps),
            'holdout_episode_n': len(holdout_eps),
            'train_plus_holdout_equals_full': len(train_eps) + len(holdout_eps) == len(full_eps),
            'episode_split_order': 'FULL_DECORELATE_THEN_SPLIT',
            'minimum_per_lane_bucket_n': MIN_LANE_N,
        },
        'pre_registered_bins': {
            'momentum_pct': ['<=0', '0_1', '1_2', '2_4', '>4'],
            'rsi14': ['<55', '55_62', '62_68', '68_72', '>=72'],
            'extension_atr': ['<0', '0_0.5', '0.5_1', '1_1.5', '>=1.5'],
            'paced_rv': ['<0.7', '0.7_1', '1_1.5', '1.5_2.5', '>=2.5'],
            'pairwise_only': ['momentum_x_rsi', 'momentum_x_extension'],
        },
        'single_regimes': singles,
        'pair_regimes': pairs,
        'stable_helpful_regimes': stable_helpful,
        'stable_harmful_regimes': stable_harmful,
        'research_decision': 'REGIME_STRUCTURE_FOUND' if stable_helpful or stable_harmful else 'NO_STABLE_REGIME_STRUCTURE',
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
        'stable_helpful_regimes': out['stable_helpful_regimes'],
        'stable_harmful_regimes': out['stable_harmful_regimes'],
        'research_decision': out['research_decision'],
        'guardrails': out['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
