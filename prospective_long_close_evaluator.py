#!/usr/bin/env python3
"""Prospective evaluator for the frozen Fourth-Vote + LONG×CLOSE shadow.

Only snapshots captured after the deployment freeze count. Historical discovery
and holdout data never enter this prospective report.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import long_close_structure_veto_shadow as candidate

OUT = Path('status/prospective-long-close-evaluation.json')
SCHEMA = 'ATLAS_PROSPECTIVE_LONG_CLOSE_EVALUATION_V1'
PROSPECTIVE_START_AT = datetime.fromisoformat('2026-08-28T09:04:14+00:00')


def evaluate(path=base.SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    rows = [r for r in rows if r['captured_at'] >= PROSPECTIVE_START_AT]
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)
    baseline = [r for r in hourly if candidate.baseline_qualified(r)]
    combined = [r for r in hourly if candidate.candidate_qualified(r)]
    vetoed = [r for r in baseline if candidate.is_vetoed(r)]

    horizons = {}
    for h in base.HORIZONS:
        b = base.stats(base.independent(baseline, h), h)
        c = base.stats(base.independent(combined, h), h)
        v = base.stats(base.independent(vetoed, h), h)
        horizons[f'{h}h'] = {
            'fourth_vote_baseline': b,
            'combined_shadow': c,
            'long_close_vetoed': v,
            'mean_delta_pct': None if b['mean_pct'] is None or c['mean_pct'] is None else round(c['mean_pct'] - b['mean_pct'], 4),
            'win_rate_delta_pct': None if b['win_rate_pct'] is None or c['win_rate_pct'] is None else round(c['win_rate_pct'] - b['win_rate_pct'], 2),
        }

    matured = {f'{h}h': horizons[f'{h}h']['fourth_vote_baseline']['n'] for h in base.HORIZONS}
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'prospective_start_at': PROSPECTIVE_START_AT.isoformat(),
        'frozen_rule': 'FOURTH_VOTE_DEMOTION_PLUS_VETO_LONG_WITH_CLOSE_PRIOR_STRUCTURE',
        'coverage': {
            'post_freeze_v6_rows': len(rows),
            'post_freeze_hourly_rows': len(hourly),
            'fourth_vote_baseline_hours': len(baseline),
            'combined_shadow_hours': len(combined),
            'long_close_vetoed_hours': len(vetoed),
            'matured_independent_baseline': matured,
            'excluded_global_parse': excluded,
        },
        'horizons': horizons,
        'evidence_status': 'PROSPECTIVE_ACTIVE' if rows else 'AWAITING_FIRST_POST_FREEZE_SNAPSHOT',
        'promotion_eligible': False,
        'promotion_note': 'Prospective tracking cannot auto-promote or mutate Production.',
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
    report = evaluate()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({
        'schema': report['schema'], 'prospective_start_at': report['prospective_start_at'],
        'coverage': report['coverage'], 'evidence_status': report['evidence_status'],
        'guardrails': report['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
