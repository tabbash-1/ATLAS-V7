#!/usr/bin/env python3
"""Prospective evaluator for the frozen fourth-vote demotion shadow.

The rule was selected before PROSPECTIVE_START_AT. Only snapshots captured after
that timestamp count toward prospective evidence. Historical rows before the
freeze are never mixed into this report. Production remains unchanged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import qualified_false_confidence_audit as base
import fourth_vote_demotion_shadow as shadow

SRC = Path('status/history/production-snapshots.jsonl')
OUT = Path('status/prospective-fourth-vote-evaluation.json')
SCHEMA = 'ATLAS_PROSPECTIVE_FOURTH_VOTE_EVALUATION_V1'
PROSPECTIVE_START_AT = datetime.fromisoformat('2026-08-28T08:56:44+00:00')


def stats(rows, horizon):
    return base.stats(base.independent(rows, horizon), horizon)


def evaluate(path=SRC):
    snapshots = base.load_snapshots(path)
    prices = base.build_price_series(snapshots)
    rows, excluded = base.flatten(snapshots)
    rows = [r for r in rows if r['captured_at'] >= PROSPECTIVE_START_AT]
    base.settle(rows, prices)
    hourly = base.hourly_dedupe(rows)

    baseline = [r for r in hourly if r['corrected_score'] >= base.THRESHOLD]
    candidate = [r for r in hourly if shadow.candidate_score(r) >= base.THRESHOLD]
    demoted = [r for r in baseline if shadow.candidate_score(r) < base.THRESHOLD]

    horizons = {}
    for h in base.HORIZONS:
        b = stats(baseline, h)
        s = stats(candidate, h)
        d = stats(demoted, h)
        horizons[f'{h}h'] = {
            'baseline': b,
            'shadow': s,
            'demoted': d,
            'mean_delta_pct': None if b['mean_pct'] is None or s['mean_pct'] is None else round(s['mean_pct'] - b['mean_pct'], 4),
            'win_rate_delta_pct': None if b['win_rate_pct'] is None or s['win_rate_pct'] is None else round(s['win_rate_pct'] - b['win_rate_pct'], 2),
        }

    matured = {f'{h}h': horizons[f'{h}h']['baseline']['n'] for h in base.HORIZONS}
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'prospective_start_at': PROSPECTIVE_START_AT.isoformat(),
        'frozen_rule': 'REMOVE_ONLY_INCREMENTAL_4_POINT_FOURTH_VOTE_PREMIUM_FOR_QUALIFICATION',
        'coverage': {
            'post_freeze_v6_rows': len(rows),
            'post_freeze_hourly_rows': len(hourly),
            'baseline_qualified_hours': len(baseline),
            'shadow_qualified_hours': len(candidate),
            'demoted_hours': len(demoted),
            'matured_independent_baseline': matured,
            'excluded_global_parse': excluded,
        },
        'horizons': horizons,
        'evidence_status': 'PROSPECTIVE_ACTIVE' if rows else 'AWAITING_FIRST_POST_FREEZE_SNAPSHOT',
        'promotion_eligible': False,
        'promotion_note': 'Prospective evidence is tracked automatically but cannot auto-promote or change Production.',
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
        'schema': report['schema'],
        'coverage': report['coverage'],
        'evidence_status': report['evidence_status'],
        'guardrails': report['guardrails'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
