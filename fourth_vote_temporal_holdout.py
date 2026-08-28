#!/usr/bin/env python3
"""Chronological holdout for the isolated fourth-vote demotion shadow."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as shadow

OUT = Path('status/fourth-vote-temporal-holdout.json')
SCHEMA = 'ATLAS_V6_FOURTH_VOTE_TEMPORAL_HOLDOUT_V1'
TRAIN_FRACTION = 0.60


def metrics(rows):
    return {f'{h}h': base.stats(base.independent(rows, h), h) for h in base.HORIZONS}


def split_hourly(rows):
    rows = sorted(rows, key=lambda r: r['captured_at'])
    times = sorted({r['captured_at'].replace(minute=0, second=0, microsecond=0) for r in rows})
    if len(times) < 2:
        return rows, [], None
    idx = max(1, min(len(times)-1, int(len(times) * TRAIN_FRACTION)))
    cutoff = times[idx]
    return [r for r in rows if r['captured_at'] < cutoff], [r for r in rows if r['captured_at'] >= cutoff], cutoff


def lane(rows):
    baseline = [r for r in rows if r['corrected_score'] >= base.THRESHOLD]
    candidate = [r for r in rows if shadow.candidate_score(r) >= base.THRESHOLD]
    demoted = [r for r in baseline if shadow.candidate_score(r) < base.THRESHOLD]
    return {'baseline': baseline, 'shadow': candidate, 'demoted': demoted}


def comparison(bm, sm):
    out = {}
    for h in base.HORIZONS:
        b, s = bm[f'{h}h'], sm[f'{h}h']
        out[f'{h}h'] = {
            'baseline_n': b['n'], 'shadow_n': s['n'],
            'mean_delta_pct': None if b['mean_pct'] is None or s['mean_pct'] is None else round(s['mean_pct'] - b['mean_pct'], 4),
            'win_rate_delta_pct': None if b['win_rate_pct'] is None or s['win_rate_pct'] is None else round(s['win_rate_pct'] - b['win_rate_pct'], 2),
        }
    return out


def run(path=base.SRC):
    snaps = base.load_snapshots(path)
    prices = base.build_price_series(snaps)
    rows, excluded = base.flatten(snaps)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    train_rows, hold_rows, cutoff = split_hourly(hourly)
    tr, ho = lane(train_rows), lane(hold_rows)
    tr_b, tr_s = metrics(tr['baseline']), metrics(tr['shadow'])
    ho_b, ho_s = metrics(ho['baseline']), metrics(ho['shadow'])
    tr_cmp, ho_cmp = comparison(tr_b, tr_s), comparison(ho_b, ho_s)

    # Predeclared holdout gate: improvement in 12h and 24h mean, no worsening
    # of their win rates, and no material 3h mean degradation (>0.10 pp).
    c3, c12, c24 = ho_cmp['3h'], ho_cmp['12h'], ho_cmp['24h']
    enough = c12['baseline_n'] >= 5 and c24['baseline_n'] >= 4 and c3['baseline_n'] >= 8
    passed = bool(
        enough and c12['mean_delta_pct'] is not None and c24['mean_delta_pct'] is not None and c3['mean_delta_pct'] is not None
        and c12['mean_delta_pct'] > 0 and c24['mean_delta_pct'] > 0
        and (c12['win_rate_delta_pct'] or 0) >= 0 and (c24['win_rate_delta_pct'] or 0) >= 0
        and c3['mean_delta_pct'] >= -0.10
    )
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'cutoff_at': cutoff.isoformat() if cutoff else None,
        'train_fraction': TRAIN_FRACTION,
        'coverage': {'snapshots': len(snaps), 'hourly_v6_rows': len(hourly), 'train_rows': len(train_rows), 'holdout_rows': len(hold_rows), 'excluded': excluded},
        'train': {'baseline_outcomes': tr_b, 'shadow_outcomes': tr_s, 'comparison': tr_cmp, 'demoted_hours': len(tr['demoted'])},
        'holdout': {'baseline_outcomes': ho_b, 'shadow_outcomes': ho_s, 'comparison': ho_cmp, 'demoted_hours': len(ho['demoted']), 'enough_evidence_for_gate': enough},
        'research_decision': 'TEMPORAL_HOLDOUT_PASS' if passed else 'TEMPORAL_HOLDOUT_FAIL_OR_INSUFFICIENT',
        'production_change_recommended': False,
        'guardrails': {'research_only': True, 'production_threshold': base.THRESHOLD, 'production_threshold_changed': False, 'production_scoring_changed': False, 'auto_promotion_enabled': False, 'live_execution': False},
        'next_decision': 'A pass permits a prospective shadow implementation only; Production remains unchanged. A fail rejects the fourth-vote demotion rule.',
    }


def main():
    r = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'schema':r['schema'],'cutoff_at':r['cutoff_at'],'holdout':r['holdout'],'research_decision':r['research_decision'],'guardrails':r['guardrails']}, sort_keys=True))

if __name__ == '__main__':
    main()
