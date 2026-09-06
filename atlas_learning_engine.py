#!/usr/bin/env python3
"""ATLAS canonical learning engine.

Unifies prospective analyst_output trade outcomes with settled Production WAIT
opportunity-cost evidence. Research-only: it diagnoses edge, missed opportunities,
and blocker quality but cannot alter Production decisions, scores, thresholds,
geometry, execution, or order routing.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyst_forward_attribution as forward
import wait_diagnostics as waits

ROOT = Path(__file__).resolve().parent
WAIT_OUTCOMES = ROOT / 'status/wait-outcomes.json'
OUT = ROOT / 'status/learning-engine-latest.json'
SCHEMA = 'ATLAS_LEARNING_ENGINE_V1'
HORIZONS = (4, 8, 12)
MIN_DIRECTIONAL_SAMPLE = 20
MIN_BLOCKER_DECISIVE_SAMPLE = 20


def _load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def _wait_horizon(hours: int) -> int:
    # Existing WAIT evidence is collected at 1/3/6/12/24H. Never interpolate
    # future outcomes; use the nearest matured checkpoint at-or-after product time.
    return 6 if hours == 4 else 12


def _trade_checkpoint_metrics(report: dict, hours: int) -> dict:
    rows = []
    for item in report.get('entries') or []:
        trade_id = item.get('id')
        # Forward attribution stores terminal settlement; canonical paper file stores
        # product checkpoints. Join by id without recomputing market outcomes.
        rows.append((trade_id, item))
    paper = _load_json(ROOT / 'status/paper-portfolio-10k-analyst-latest.json', {'trades': []})
    by_id = {x.get('id'): x for x in paper.get('trades') or []}
    values = []
    for trade_id, _ in rows:
        tr = by_id.get(trade_id) or {}
        cp = next((x for x in tr.get('product_window_checkpoints') or [] if int(x.get('checkpoint_h') or 0) == hours), None)
        if not cp or not cp.get('matured'):
            continue
        r = cp.get('r_multiple')
        if isinstance(r, (int, float)):
            values.append(float(r))
    return {
        'n': len(values),
        'avg_r': round(sum(values) / len(values), 4) if values else None,
        'positive_pct': round(100 * sum(v > 0 for v in values) / len(values), 2) if values else None,
        'sample_status': 'VALIDATION_SAMPLE' if len(values) >= MIN_DIRECTIONAL_SAMPLE else 'SMALL_SAMPLE',
    }


def _wait_metrics(payload: dict, hours: int) -> dict:
    source_h = _wait_horizon(hours)
    d = waits.diagnose(payload, source_h)
    overall = d.get('overall') or {}
    c = overall.get('classification_counts') or {}
    missed = int(c.get('MISSED_DIRECTIONAL_OPPORTUNITY') or 0)
    protected = int(c.get('WAIT_PROTECTED_CAPITAL') or 0)
    decisive = missed + protected
    return {
        'source_checkpoint_h': source_h,
        'settled': int(overall.get('settled') or 0),
        'decisive': decisive,
        'missed': missed,
        'protected': protected,
        'missed_opportunity_rate_pct': round(100 * missed / decisive, 2) if decisive else None,
        'sample_status': 'VALIDATION_SAMPLE' if decisive >= MIN_DIRECTIONAL_SAMPLE else 'SMALL_SAMPLE',
    }


def _blocker_attribution(payload: dict) -> list[dict]:
    d = waits.diagnose(payload, 12)
    out = []
    for name, st in sorted((d.get('by_blocker') or {}).items()):
        c = st.get('classification_counts') or {}
        missed = int(c.get('MISSED_DIRECTIONAL_OPPORTUNITY') or 0)
        protected = int(c.get('WAIT_PROTECTED_CAPITAL') or 0)
        decisive = missed + protected
        if decisive == 0:
            continue
        missed_rate = 100 * missed / decisive
        if decisive < MIN_BLOCKER_DECISIVE_SAMPLE:
            verdict = 'INSUFFICIENT_SAMPLE'
        elif missed_rate >= 65:
            verdict = 'POSSIBLY_OVER_RESTRICTIVE_RESEARCH_ONLY'
        elif missed_rate <= 35:
            verdict = 'LIKELY_PROTECTIVE'
        else:
            verdict = 'MIXED'
        out.append({
            'blocker': name,
            'decisive_n': decisive,
            'missed': missed,
            'protected': protected,
            'missed_rate_pct': round(missed_rate, 2),
            'verdict': verdict,
            'production_change_authorized': False,
        })
    out.sort(key=lambda x: (x['verdict'] == 'POSSIBLY_OVER_RESTRICTIVE_RESEARCH_ONLY', x['missed_rate_pct'], x['decisive_n']), reverse=True)
    return out


def build() -> dict:
    forward_report = forward.build()
    wait_payload = _load_json(WAIT_OUTCOMES, {'records': []})
    trade_by_h = {f'{h}h': _trade_checkpoint_metrics(forward_report, h) for h in HORIZONS}
    wait_by_h = {f'{h}h': _wait_metrics(wait_payload, h) for h in HORIZONS}
    blockers = _blocker_attribution(wait_payload)
    closed = int((forward_report.get('counts') or {}).get('matured_12h_terminal') or 0)
    entries = int((forward_report.get('counts') or {}).get('entries') or 0)
    decisive_waits = int((wait_by_h.get('12h') or {}).get('decisive') or 0)
    missed_waits = int((wait_by_h.get('12h') or {}).get('missed') or 0)
    protected_waits = int((wait_by_h.get('12h') or {}).get('protected') or 0)
    enough_trade = closed >= MIN_DIRECTIONAL_SAMPLE
    enough_wait = decisive_waits >= MIN_DIRECTIONAL_SAMPLE
    return {
        'schema': SCHEMA,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'canonical_contract': 'analyst_output',
        'product_horizon': '4-12H',
        'purpose': 'Unify canonical forward trade outcomes and settled WAIT opportunity cost into one evidence contract.',
        'methodology': {
            'trade_truth': 'Frozen prospective analyst_output entries and canonical paper 4/8/12H checkpoints only.',
            'wait_truth': 'Settled Production WAIT opportunity-cost records; no hindsight direction is invented when consensus was absent.',
            'causal_claims': False,
            'future_leakage_allowed': False,
            'automatic_learning_updates': False,
        },
        'evidence': {
            'trade_entries': entries,
            'trade_closed_12h': closed,
            'wait_decisive_12h': decisive_waits,
            'wait_missed_12h': missed_waits,
            'wait_protected_12h': protected_waits,
            'trade_by_horizon': trade_by_h,
            'wait_by_horizon': wait_by_h,
        },
        'blocker_attribution_12h': blockers,
        'proof_status': {
            'trade_sample_sufficient': enough_trade,
            'wait_sample_sufficient': enough_wait,
            'edge_proven': False,
            'status': 'EVIDENCE_COLLECTION' if not (enough_trade and enough_wait) else 'READY_FOR_CONTROLLED_OUT_OF_SAMPLE_REVIEW',
            'reason': 'ATLAS does not declare edge proven from small samples; promotion requires controlled out-of-sample evidence.',
        },
        'next_actions': {
            'review_over_restrictive_blockers': [x['blocker'] for x in blockers if x['verdict'] == 'POSSIBLY_OVER_RESTRICTIVE_RESEARCH_ONLY'],
            'auto_promote': False,
            'auto_change_threshold': False,
            'auto_change_weights': False,
        },
        'safety': {
            'research_only': True,
            'paper_only': True,
            'analysis_only': True,
            'live_execution': False,
            'can_override_production': False,
            'can_change_score': False,
            'can_change_threshold': False,
            'can_change_geometry': False,
            'can_change_decision': False,
        },
    }


def main():
    report = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'schema': report['schema'], 'evidence': report['evidence'], 'proof_status': report['proof_status']}, sort_keys=True))


if __name__ == '__main__':
    main()
