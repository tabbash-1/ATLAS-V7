#!/usr/bin/env python3
"""Residual autopsy after the frozen combined shadow.

Scope is intentionally narrow: V6 hourly observations that survive BOTH the
fourth-vote demotion shadow and the LONG+CLOSE prior-structure veto. The goal is
to identify one additional stable harmful interaction, especially at 24h,
without changing Production.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as fourth
import long_close_structure_veto_shadow as lc

OUT = Path('status/post-combined-shadow-residual-autopsy.json')
SCHEMA = 'ATLAS_V6_POST_COMBINED_SHADOW_RESIDUAL_AUTOPSY_V1'


def volume_bin(rv):
    x = base.fnum(rv, 0.0) or 0.0
    if x < 0.5: return '<0.50'
    if x < 0.8: return '0.50-0.79'
    if x < 1.0: return '0.80-0.99'
    if x < 1.5: return '1.00-1.49'
    return '>=1.50'


def score_bin(score):
    x = int(base.round_score(score))
    if x <= 69: return '68-69'
    if x <= 72: return '70-72'
    if x <= 76: return '73-76'
    return '77+'


def keymap(r):
    direction = str(r.get('direction') or 'UNKNOWN')
    obstacle = str(r.get('obstacle_reason') or 'UNKNOWN')
    rs = str(r.get('rs_reason') or 'UNKNOWN')
    vb = volume_bin(r.get('relative_volume_replayed'))
    sb = score_bin(fourth.candidate_score(r))
    return {
        'direction': direction,
        'obstacle': obstacle,
        'relative_strength': rs,
        'volume_bin': vb,
        'shadow_score_bin': sb,
        'direction_x_obstacle': f'{direction}|{obstacle}',
        'direction_x_rs': f'{direction}|{rs}',
        'direction_x_volume': f'{direction}|{vb}',
        'direction_x_score': f'{direction}|{sb}',
        'rs_x_obstacle': f'{rs}|{obstacle}',
        'volume_x_obstacle': f'{vb}|{obstacle}',
        'score_x_rs': f'{sb}|{rs}',
        'score_x_obstacle': f'{sb}|{obstacle}',
    }


def split(rows):
    rows = sorted(rows, key=lambda r: r['captured_at'])
    hours = sorted({r['captured_at'].replace(minute=0, second=0, microsecond=0) for r in rows})
    if len(hours) < 2:
        return rows, [], None
    idx = max(1, min(len(hours)-1, int(len(hours)*0.60)))
    cutoff = hours[idx]
    return [r for r in rows if r['captured_at'] < cutoff], [r for r in rows if r['captured_at'] >= cutoff], cutoff


def grouped(rows, field, horizon):
    buckets = defaultdict(list)
    for r in rows:
        buckets[keymap(r)[field]].append(r)
    return {k: base.stats(base.independent(v, horizon), horizon) for k, v in sorted(buckets.items())}


def stable_bad(a, b, h):
    return bool(
        h in (12, 24)
        and a.get('n', 0) >= 3 and b.get('n', 0) >= 3
        and a.get('mean_pct') is not None and b.get('mean_pct') is not None
        and a['mean_pct'] < 0 and b['mean_pct'] < 0
        and (a.get('win_rate_pct') or 0) < 50 and (b.get('win_rate_pct') or 0) < 50
    )


def stable_good(a, b, h):
    return bool(
        h in (12, 24)
        and a.get('n', 0) >= 3 and b.get('n', 0) >= 3
        and a.get('mean_pct') is not None and b.get('mean_pct') is not None
        and a['mean_pct'] > 0 and b['mean_pct'] > 0
        and (a.get('win_rate_pct') or 0) >= 50 and (b.get('win_rate_pct') or 0) >= 50
    )


def diagnostics(train, hold, all_rows):
    factors = [
        'direction','obstacle','relative_strength','volume_bin','shadow_score_bin',
        'direction_x_obstacle','direction_x_rs','direction_x_volume','direction_x_score',
        'rs_x_obstacle','volume_x_obstacle','score_x_rs','score_x_obstacle',
    ]
    tables, harmful, positive = {}, [], []
    for factor in factors:
        tables[factor] = {}
        for h in (3, 12, 24):
            full = grouped(all_rows, factor, h)
            tr = grouped(train, factor, h)
            ho = grouped(hold, factor, h)
            rows_out = {}
            for k in sorted(set(full) | set(tr) | set(ho)):
                f = full.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                a = tr.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                b = ho.get(k, {'n':0,'mean_pct':None,'win_rate_pct':None})
                bad = stable_bad(a, b, h)
                good = stable_good(a, b, h)
                rows_out[k] = {'full':f,'train':a,'holdout':b,'stable_harmful':bad,'stable_positive':good}
                item = {'factor':factor,'bucket':k,'horizon_h':h,'full':f,'train':a,'holdout':b}
                if bad: harmful.append(item)
                if good: positive.append(item)
            tables[factor][f'{h}h'] = rows_out
    harmful.sort(key=lambda x: (0 if x['horizon_h'] == 24 else 1, x['full'].get('mean_pct') or 0, -(x['full'].get('n') or 0)))
    positive.sort(key=lambda x: (0 if x['horizon_h'] == 24 else 1, -(x['full'].get('mean_pct') or 0), -(x['full'].get('n') or 0)))
    return tables, harmful, positive


def run(path=base.SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    retained = [r for r in hourly if lc.candidate_qualified(r)]
    train, hold, cutoff = split(retained)
    tables, harmful, positive = diagnostics(train, hold, retained)
    overall = {f'{h}h':base.stats(base.independent(retained,h),h) for h in base.HORIZONS}
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'V6_ROWS_RETAINED_BY_FOURTH_VOTE_AND_LONG_CLOSE_VETO_SHADOW',
        'coverage': {
            'snapshots': len(snapshots), 'hourly_v6_rows': len(hourly),
            'retained_combined_shadow_hours': len(retained),
            'train_rows': len(train), 'holdout_rows': len(hold),
            'cutoff_at': cutoff.isoformat() if cutoff else None, 'excluded': excluded,
        },
        'overall_retained_outcomes': overall,
        'stable_harmful_buckets': harmful,
        'stable_positive_buckets': positive,
        'factor_tables': tables,
        'diagnostic_decision': 'INVESTIGATE_TOP_STABLE_HARMFUL_BUCKET' if harmful else 'NO_STABLE_THIRD_BUCKET_FOUND',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True, 'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False, 'production_scoring_changed': False,
            'fourth_vote_shadow_changed': False, 'long_close_shadow_changed': False,
            'auto_promotion_enabled': False, 'can_override_production': False, 'live_execution': False,
        },
        'next_decision': 'Only one stable harmful bucket that remains negative in both train and holdout may seed an isolated third shadow. Prefer 24h evidence; do not stack multiple fixes.',
    }


def main():
    r = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': r['schema'], 'coverage': r['coverage'],
        'overall': r['overall_retained_outcomes'],
        'stable_harmful_buckets': r['stable_harmful_buckets'][:10],
        'stable_positive_buckets': r['stable_positive_buckets'][:6],
        'diagnostic_decision': r['diagnostic_decision'], 'guardrails': r['guardrails'],
    }, sort_keys=True))

if __name__ == '__main__':
    main()
