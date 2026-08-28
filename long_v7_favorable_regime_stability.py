#!/usr/bin/env python3
"""Stress-test the selected LONG V7 favorable regime.

Selected research regime (post-selection, NOT a clean holdout):
- 24h momentum >1% and <=2%
- price extension above EMA20 >=0.5 and <1.0 ATR

This audit does not re-select thresholds. It asks whether the five observed
regime episodes are diversified across symbols/days and whether the positive
mean survives leave-one-symbol-out and leave-one-day-out. Because the regime was
selected after viewing Train+Holdout, passing this audit permits only a frozen
prospective shadow, never Production promotion.
Evaluation trigger note: selected regime boundaries are frozen for V1.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_v7_raw_representation_audit as raw

OUT = Path('status/long-v7-favorable-regime-stability.json')
SCHEMA = 'ATLAS_LONG_V7_FAVORABLE_REGIME_STABILITY_V1'
H = 12


def is_regime(r):
    m = base.fnum(r.get('momentum_24h_pct'))
    x = base.fnum(r.get('price_extension_atr'))
    return m is not None and x is not None and 1.0 < m <= 2.0 and 0.5 <= x < 1.0


def stats(rows):
    return base.stats(rows, H)


def _day(r):
    ts = r.get('captured_at')
    if hasattr(ts, 'date'):
        return ts.date().isoformat()
    return str(ts)[:10]


def leave_one(rows, keyfn):
    keys = sorted({keyfn(r) for r in rows})
    tests = []
    for key in keys:
        sub = [r for r in rows if keyfn(r) != key]
        s = stats(sub)
        tests.append({'left_out': key, **s})
    eligible = [x for x in tests if x.get('n', 0) >= 2 and x.get('mean_pct') is not None]
    return {
        'tests': tests,
        'eligible_tests': len(eligible),
        'all_mean_positive': bool(eligible) and all(x['mean_pct'] > 0 for x in eligible),
        'minimum_leave_one_mean_pct': None if not eligible else min(x['mean_pct'] for x in eligible),
    }


def run(path=base.SRC):
    snaps, hourly = raw.load_rows(path)
    eps = raw.mature_episodes(hourly)
    cohort = [r for r in eps if is_regime(r)]
    syms = Counter(str(r.get('symbol')) for r in cohort)
    days = Counter(_day(r) for r in cohort)
    by_symbol = leave_one(cohort, lambda r: str(r.get('symbol')))
    by_day = leave_one(cohort, _day)
    s = stats(cohort)
    diversified = len(syms) >= 3 and len(days) >= 3
    stable = s.get('n', 0) >= 5 and s.get('mean_pct') is not None and s['mean_pct'] > 0 and diversified and by_symbol['all_mean_positive'] and by_day['all_mean_positive']
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'selected_regime': {
            'momentum_24h_pct': '>1 and <=2',
            'price_extension_atr': '>=0.5 and <1.0',
            'selection_warning': 'POST_SELECTION_STRESS_TEST_NOT_CLEAN_HOLDOUT',
        },
        'cohort': s,
        'symbol_counts': dict(syms),
        'day_counts': dict(days),
        'leave_one_symbol_out': by_symbol,
        'leave_one_day_out': by_day,
        'diversified_across_at_least_3_symbols_and_3_days': diversified,
        'stability_passed': stable,
        'research_decision': 'FREEZE_AS_PROSPECTIVE_FAVORABLE_LONG_REGIME' if stable else 'KEEP_DIAGNOSTIC_ONLY',
        'production_change_recommended': False,
        'guardrails': {
            'research_only': True,
            'post_selection_test': True,
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
