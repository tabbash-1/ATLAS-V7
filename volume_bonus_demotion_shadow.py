#!/usr/bin/env python3
"""Research-only V6 volume-bonus demotion shadow.

Uses the qualified false-confidence audit's replayed V6 observations. The shadow
changes exactly one thing: a positive volume bonus may improve ranking, but it
may not be the component that alone lifts an observation from below threshold
68 to qualified. Production scoring and threshold remain untouched.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base

OUT = Path('status/volume-bonus-demotion-shadow.json')
SCHEMA = 'ATLAS_V6_VOLUME_BONUS_DEMOTION_SHADOW_V1'


def candidate_score(r):
    """Remove only the positive volume bonus for threshold qualification."""
    return base.round_score(r['corrected_score'] - max(0.0, base.fnum(r.get('volume_bonus'), 0.0) or 0.0))


def metrics(rows):
    return {f'{h}h': base.stats(base.independent(rows, h), h) for h in base.HORIZONS}


def compare(path=base.SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)

    baseline = [r for r in hourly if r['corrected_score'] >= base.THRESHOLD]
    shadow = [r for r in hourly if candidate_score(r) >= base.THRESHOLD]
    demoted = [r for r in baseline if candidate_score(r) < base.THRESHOLD]

    result = {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'hypothesis': 'Volume may rank strong setups higher, but should not by itself be the final component that crosses Production threshold 68.',
        'coverage': {
            'snapshots': len(snapshots),
            'hourly_v6_rows': len(hourly),
            'baseline_qualified_hours': len(baseline),
            'shadow_qualified_hours': len(shadow),
            'demoted_hours': len(demoted),
            'excluded': excluded,
        },
        'baseline_outcomes': metrics(baseline),
        'shadow_outcomes': metrics(shadow),
        'demoted_outcomes': metrics(demoted),
        'retention_pct': round(100.0 * len(shadow) / len(baseline), 2) if baseline else None,
        'guardrails': {
            'research_only': True,
            'production_threshold': base.THRESHOLD,
            'production_threshold_changed': False,
            'production_scoring_changed': False,
            'auto_promotion_enabled': False,
            'live_execution': False,
        },
    }

    # Predeclared evaluation: shadow must improve mean and win rate at 12h and
    # 24h without materially worsening 3h mean by more than 0.10 percentage point.
    checks = {}
    for h in base.HORIZONS:
        b = result['baseline_outcomes'][f'{h}h']
        s = result['shadow_outcomes'][f'{h}h']
        checks[f'{h}h'] = {
            'baseline_n': b['n'], 'shadow_n': s['n'],
            'mean_delta_pct': None if b['mean_pct'] is None or s['mean_pct'] is None else round(s['mean_pct'] - b['mean_pct'], 4),
            'win_rate_delta_pct': None if b['win_rate_pct'] is None or s['win_rate_pct'] is None else round(s['win_rate_pct'] - b['win_rate_pct'], 2),
        }
    result['comparison'] = checks
    c3, c12, c24 = checks['3h'], checks['12h'], checks['24h']
    qualifies = bool(
        c12['mean_delta_pct'] is not None and c24['mean_delta_pct'] is not None and c3['mean_delta_pct'] is not None
        and c12['mean_delta_pct'] > 0 and c24['mean_delta_pct'] > 0
        and (c12['win_rate_delta_pct'] or 0) > 0 and (c24['win_rate_delta_pct'] or 0) > 0
        and c3['mean_delta_pct'] >= -0.10
        and len(demoted) >= 8
    )
    result['research_decision'] = 'ADVANCE_TO_TEMPORAL_HOLDOUT_SHADOW' if qualifies else 'REJECT_VOLUME_DEMOTION_SHADOW'
    result['production_change_recommended'] = False
    return result


def main():
    r = compare()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': r['schema'], 'coverage': r['coverage'], 'comparison': r['comparison'],
        'research_decision': r['research_decision'], 'guardrails': r['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
