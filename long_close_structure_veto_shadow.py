#!/usr/bin/env python3
"""Research-only interaction shadow: LONG + CLOSE_PRIOR_STRUCTURE veto.

Baseline is the already validated fourth-vote demotion shadow. This candidate
changes exactly one additional interaction: observations whose direction is LONG
and whose prior-structure obstacle is CLOSE are not allowed to qualify. SHORT
CLOSE observations and every other component remain untouched.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as fourth

OUT = Path('status/long-close-structure-veto-shadow.json')
SCHEMA = 'ATLAS_V6_LONG_CLOSE_STRUCTURE_VETO_SHADOW_V1'


def is_vetoed(r):
    return str(r.get('direction') or '') == 'LONG' and str(r.get('obstacle_reason') or '') == 'CLOSE_PRIOR_STRUCTURE'


def baseline_qualified(r):
    return fourth.candidate_score(r) >= base.THRESHOLD


def candidate_qualified(r):
    return baseline_qualified(r) and not is_vetoed(r)


def metrics(rows):
    return {f'{h}h': base.stats(base.independent(rows, h), h) for h in base.HORIZONS}


def split(rows):
    rows = sorted(rows, key=lambda r: r['captured_at'])
    hours = sorted({r['captured_at'].replace(minute=0, second=0, microsecond=0) for r in rows})
    if len(hours) < 2:
        return rows, [], None
    idx = max(1, min(len(hours)-1, int(len(hours)*0.60)))
    cutoff = hours[idx]
    return [r for r in rows if r['captured_at'] < cutoff], [r for r in rows if r['captured_at'] >= cutoff], cutoff


def compare_metrics(bm, cm):
    out = {}
    for h in base.HORIZONS:
        b, c = bm[f'{h}h'], cm[f'{h}h']
        out[f'{h}h'] = {
            'baseline_n': b['n'], 'candidate_n': c['n'],
            'mean_delta_pct': None if b['mean_pct'] is None or c['mean_pct'] is None else round(c['mean_pct'] - b['mean_pct'], 4),
            'win_rate_delta_pct': None if b['win_rate_pct'] is None or c['win_rate_pct'] is None else round(c['win_rate_pct'] - b['win_rate_pct'], 2),
        }
    return out


def lane(rows):
    baseline = [r for r in rows if baseline_qualified(r)]
    candidate = [r for r in rows if candidate_qualified(r)]
    vetoed = [r for r in baseline if is_vetoed(r)]
    return baseline, candidate, vetoed


def run(path=base.SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)

    train_rows, hold_rows, cutoff = split(hourly)
    full_b, full_c, full_v = lane(hourly)
    tr_b, tr_c, tr_v = lane(train_rows)
    ho_b, ho_c, ho_v = lane(hold_rows)

    full_bm, full_cm = metrics(full_b), metrics(full_c)
    tr_bm, tr_cm = metrics(tr_b), metrics(tr_c)
    ho_bm, ho_cm = metrics(ho_b), metrics(ho_c)
    full_cmp = compare_metrics(full_bm, full_cm)
    train_cmp = compare_metrics(tr_bm, tr_cm)
    hold_cmp = compare_metrics(ho_bm, ho_cm)

    # Predeclared gate: full and holdout 12h must improve in both mean and win
    # rate; holdout 3h may not degrade by >0.10 pp; 24h may be neutral if its
    # independent sample is too small, but must not degrade when measurable.
    h3, h12, h24 = hold_cmp['3h'], hold_cmp['12h'], hold_cmp['24h']
    enough = h12['baseline_n'] >= 8 and base.stats(base.independent(ho_v, 12), 12)['n'] >= 3
    h24_ok = h24['mean_delta_pct'] is None or h24['mean_delta_pct'] >= 0
    passed = bool(
        enough
        and full_cmp['12h']['mean_delta_pct'] is not None and full_cmp['12h']['mean_delta_pct'] > 0
        and (full_cmp['12h']['win_rate_delta_pct'] or 0) > 0
        and h12['mean_delta_pct'] is not None and h12['mean_delta_pct'] > 0
        and (h12['win_rate_delta_pct'] or 0) > 0
        and h3['mean_delta_pct'] is not None and h3['mean_delta_pct'] >= -0.10
        and h24_ok
    )

    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'After fourth-vote demotion, LONG candidates facing CLOSE prior structure are a direction-specific false-confidence interaction and should be vetoed in shadow only.',
        'coverage': {
            'snapshots': len(snapshots), 'hourly_v6_rows': len(hourly),
            'cutoff_at': cutoff.isoformat() if cutoff else None,
            'full_baseline_hours': len(full_b), 'full_candidate_hours': len(full_c), 'full_vetoed_hours': len(full_v),
            'train_baseline_hours': len(tr_b), 'train_candidate_hours': len(tr_c), 'train_vetoed_hours': len(tr_v),
            'holdout_baseline_hours': len(ho_b), 'holdout_candidate_hours': len(ho_c), 'holdout_vetoed_hours': len(ho_v),
            'excluded': excluded,
        },
        'full': {'baseline': full_bm, 'candidate': full_cm, 'vetoed': metrics(full_v), 'comparison': full_cmp},
        'train': {'baseline': tr_bm, 'candidate': tr_cm, 'vetoed': metrics(tr_v), 'comparison': train_cmp},
        'holdout': {'baseline': ho_bm, 'candidate': ho_cm, 'vetoed': metrics(ho_v), 'comparison': hold_cmp, 'enough_evidence_for_gate': enough},
        'research_decision': 'ADVANCE_LONG_CLOSE_VETO_TO_PROSPECTIVE_SHADOW' if passed else 'REJECT_LONG_CLOSE_STRUCTURE_VETO',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True, 'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False, 'production_scoring_changed': False,
            'fourth_vote_baseline_changed': False, 'auto_promotion_enabled': False,
            'can_override_production': False, 'live_execution': False,
        },
    }


def main():
    r = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': r['schema'], 'coverage': r['coverage'],
        'full_comparison': r['full']['comparison'],
        'holdout_comparison': r['holdout']['comparison'],
        'holdout_vetoed': r['holdout']['vetoed'],
        'research_decision': r['research_decision'], 'guardrails': r['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
