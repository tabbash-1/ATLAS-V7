#!/usr/bin/env python3
"""ATLAS prospective attribution for canonical analyst_output forward evidence.

Research/evaluation only. It freezes explanatory context around already-captured
Production analyses and summarizes matured 4/8/12H outcomes. It never changes
scores, thresholds, Production decisions, or order routing.
"""
from __future__ import annotations
import json, math, pathlib
from collections import defaultdict
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent
HISTORY = ROOT / 'status/history/analyst-output-snapshots.jsonl'
COHORT = ROOT / 'status/history/paper-portfolio-10k-analyst-cohort.jsonl'
FORWARD = ROOT / 'status/paper-portfolio-10k-analyst-latest.json'
OUT = ROOT / 'status/analyst-forward-attribution-latest.json'
SCHEMA = 'ATLAS_ANALYST_FORWARD_ATTRIBUTION_V1'


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def _jsonl(path):
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def score_bucket(v):
    x = _num(v)
    if x is None:
        return 'UNKNOWN'
    if x < 68:
        return '<68'
    if x < 72:
        return '68-71'
    if x < 76:
        return '72-75'
    if x < 80:
        return '76-79'
    return '80+'


def compact_context(d: dict[str, Any]) -> dict[str, Any]:
    a = d.get('analyst_output') or {}
    sa = d.get('score_attribution') or {}
    ind = d.get('indicators') or {}
    sg = d.get('structural_geometry') or {}
    breakout = sg.get('breakout') or {}
    gate = a.get('setup_quality_gate') or d.get('setup_quality_gate') or {}
    return {
        'schema': 'ATLAS_FORWARD_ATTRIBUTION_CONTEXT_V1',
        'symbol': d.get('symbol'),
        'decision': a.get('decision'),
        'candidate_direction': d.get('candidate_direction'),
        'score': _num(a.get('confidence') if a.get('confidence') is not None else d.get('score')),
        'threshold': _num(a.get('signal_threshold') if a.get('signal_threshold') is not None else d.get('signal_threshold')),
        'score_bucket': score_bucket(a.get('confidence') if a.get('confidence') is not None else d.get('score')),
        'playbook': a.get('playbook') or d.get('playbook'),
        'regime': a.get('regime') or d.get('regime'),
        'quality_gate_status': gate.get('status'),
        'quality_gate_reason': gate.get('reason'),
        'production_qualified_raw': bool(a.get('production_qualified_raw', d.get('production_signal_qualified'))),
        'geometry_ready_raw': bool(a.get('geometry_ready_raw', (d.get('geometry_gate') or {}).get('qualified'))),
        'direction_votes': d.get('direction_votes'),
        'direction_votes_long': d.get('direction_votes_long'),
        'direction_votes_short': d.get('direction_votes_short'),
        'relative_strength_score': _num(d.get('relative_strength_score')),
        'futures_available': d.get('futures_available'),
        'futures_provider': d.get('futures_provider'),
        'futures_score': _num(d.get('futures_score')),
        'volume_quality': _num(d.get('volume_quality')),
        'relative_volume': _num(d.get('relative_volume')),
        'trend_base': _num(sa.get('trend_base')),
        'volume_bonus': _num(sa.get('volume_bonus')),
        'relative_strength_adjustment': _num(sa.get('relative_strength_adjustment')),
        'relative_strength_reason': sa.get('relative_strength_reason'),
        'futures_adjustment': _num(sa.get('futures_adjustment')),
        'futures_reason': sa.get('futures_reason'),
        'obstacle_adjustment': _num(sa.get('obstacle_adjustment')),
        'obstacle_reason': sa.get('obstacle_reason'),
        'momentum_adjustment': _num(sa.get('momentum_adjustment')),
        'market_breadth_adjustment': _num(sa.get('market_breadth_adjustment')),
        'extension_guard_adjustment': _num(sa.get('extension_guard_adjustment')),
        'extension_guard_reason': sa.get('extension_guard_reason'),
        'rsi14': _num(ind.get('rsi14')),
        'atr14': _num(ind.get('atr14')),
        'momentum_24h_pct': _num(ind.get('momentum_24h_pct')),
        'breakout_confirmed': breakout.get('confirmed'),
        'beyond_prior_24h_range': breakout.get('beyond_prior_24h_range'),
        'current_body_atr': _num(breakout.get('current_body_atr')),
        'paced_relative_volume': _num(breakout.get('paced_relative_volume')),
        'structural_geometry_source': sg.get('source'),
        'data_degraded': bool(a.get('data_degraded', d.get('data_degraded', False))),
        'primary_reason': a.get('primary_reason'),
        'reasons': list(a.get('reasons') or []),
        'invalidation': a.get('invalidation'),
    }


def evidence_tags(ctx):
    tags = []
    direction = str(ctx.get('decision') or '').upper()
    rsi = _num(ctx.get('rsi14'))
    if ctx.get('data_degraded'):
        tags.append('DATA_DEGRADED')
    if str(ctx.get('futures_reason') or '').upper() == 'OPPOSED' or (_num(ctx.get('futures_adjustment')) or 0) < 0:
        tags.append('DERIVATIVES_OPPOSED')
    if direction == 'LONG' and rsi is not None and rsi >= 75:
        tags.append('LONG_RSI_EXTENDED')
    if direction == 'SHORT' and rsi is not None and rsi <= 25:
        tags.append('SHORT_RSI_EXTENDED')
    rv = _num(ctx.get('relative_volume'))
    if rv is not None and rv < 0.8:
        tags.append('WEAK_RELATIVE_VOLUME')
    if 'BREAKOUT' in str(ctx.get('playbook') or '').upper() and ctx.get('breakout_confirmed') is False:
        tags.append('BREAKOUT_NOT_CONFIRMED')
    score = _num(ctx.get('score')); threshold = _num(ctx.get('threshold'))
    if score is not None and threshold is not None and score - threshold <= 2:
        tags.append('MARGINAL_SCORE_CLEARANCE')
    if not tags:
        tags.append('NO_OBVIOUS_PREENTRY_WEAKNESS')
    return tags


def failure_hypothesis(ctx, settlement):
    """Deterministic evidence label, explicitly not a causal claim."""
    status = str(settlement.get('status') or '')
    r = _num(settlement.get('r_multiple'))
    if status == 'MARKET_DATA_ERROR':
        return 'EVALUATION_DATA_FAILURE'
    if r is None:
        return 'PENDING_OR_UNRESOLVED'
    if r >= 0:
        return 'NO_FAILURE_POSITIVE_OUTCOME'
    tags = evidence_tags(ctx)
    priority = [
        ('DATA_DEGRADED', 'DATA_HEALTH_RISK'),
        ('BREAKOUT_NOT_CONFIRMED', 'STRUCTURE_CONFIRMATION_RISK'),
        ('DERIVATIVES_OPPOSED', 'DERIVATIVES_CONTRADICTION_RISK'),
        ('LONG_RSI_EXTENDED', 'MOMENTUM_EXTENSION_RISK'),
        ('SHORT_RSI_EXTENDED', 'MOMENTUM_EXTENSION_RISK'),
        ('WEAK_RELATIVE_VOLUME', 'VOLUME_CONFIRMATION_RISK'),
        ('MARGINAL_SCORE_CLEARANCE', 'MARGINAL_QUALIFICATION_RISK'),
    ]
    for tag, label in priority:
        if tag in tags:
            return label
    return 'SETUP_OR_TIMING_RISK'


def _metrics(rows):
    vals = [_num(x.get('r')) for x in rows]
    vals = [x for x in vals if x is not None]
    mfes = [_num(x.get('mfe_r')) for x in rows]; mfes = [x for x in mfes if x is not None]
    maes = [_num(x.get('mae_r')) for x in rows]; maes = [x for x in maes if x is not None]
    return {
        'n': len(vals),
        'avg_r': round(sum(vals)/len(vals), 4) if vals else None,
        'positive_pct': round(100*sum(x > 0 for x in vals)/len(vals), 2) if vals else None,
        'avg_mfe_r': round(sum(mfes)/len(mfes), 4) if mfes else None,
        'avg_mae_r': round(sum(maes)/len(maes), 4) if maes else None,
        'tp1_pct': round(100*sum(bool(x.get('tp1')) for x in rows)/len(rows), 2) if rows else None,
        'tp2_pct': round(100*sum(x.get('status') == 'WIN_TP' for x in rows)/len(rows), 2) if rows else None,
        'sl_pct': round(100*sum(x.get('status') == 'LOSS' for x in rows)/len(rows), 2) if rows else None,
    }


def build():
    history = _jsonl(HISTORY)
    cohort = _jsonl(COHORT)
    forward = json.loads(FORWARD.read_text()) if FORWARD.exists() else {'trades': []}
    by_capture = {x.get('captured_at'): x for x in history}
    trade_by_id = {x.get('id'): x for x in forward.get('trades') or []}
    entries = []
    matured = []
    for row in cohort:
        snap = by_capture.get(row.get('captured_at')) or {}
        decision = (snap.get('decisions') or {}).get(row.get('symbol')) or {}
        ctx = compact_context(decision) if decision else {'schema':'ATLAS_FORWARD_ATTRIBUTION_CONTEXT_V1','symbol':row.get('symbol'),'decision':row.get('direction'),'context_missing':True}
        tr = trade_by_id.get(row.get('id')) or {}
        settlement = tr.get('settlement') or {}
        tags = evidence_tags(ctx) if not ctx.get('context_missing') else ['CONTEXT_MISSING']
        item = {
            'id': row.get('id'),
            'captured_at': row.get('captured_at'),
            'symbol': row.get('symbol'),
            'direction': row.get('direction'),
            'context': ctx,
            'evidence_tags': tags,
            'settlement': settlement,
            'failure_hypothesis': failure_hypothesis(ctx, settlement),
            'causal_claim': False,
        }
        entries.append(item)
        r = _num(settlement.get('r_multiple'))
        if settlement.get('terminal') and r is not None:
            matured.append({
                'id': row.get('id'), 'symbol': row.get('symbol'), 'direction': row.get('direction'),
                'playbook': ctx.get('playbook'), 'regime': ctx.get('regime'), 'score_bucket': ctx.get('score_bucket'),
                'quality_gate_status': ctx.get('quality_gate_status'), 'r': r,
                'mfe_r': _num(settlement.get('mfe_r')), 'mae_r': _num(settlement.get('mae_r')),
                'tp1': bool(settlement.get('tp1_reached')), 'status': settlement.get('status'),
                'failure_hypothesis': item['failure_hypothesis'],
            })
    groups = {}
    for field in ('symbol','direction','playbook','regime','score_bucket','quality_gate_status','failure_hypothesis'):
        bag = defaultdict(list)
        for x in matured:
            bag[str(x.get(field) or 'UNKNOWN')].append(x)
        groups[field] = {k:_metrics(v) for k,v in sorted(bag.items())}
    return {
        'schema': SCHEMA,
        'canonical_contract': 'analyst_output',
        'product_horizon': '4-12H',
        'analysis_only': True,
        'paper_only': True,
        'live_execution': False,
        'can_override_production': False,
        'can_change_score': False,
        'can_change_threshold': False,
        'methodology': 'Frozen pre-entry evidence context joined to prospective 4/8/12H evaluation. Failure labels are deterministic hypotheses, not causal proof.',
        'counts': {'entries':len(entries),'context_complete':sum(not x['context'].get('context_missing') for x in entries),'matured_12h_terminal':len(matured),'pending':len(entries)-len(matured)},
        'matured_12h_metrics': _metrics(matured),
        'breakdowns': groups,
        'entries': entries,
    }


def main():
    out = build()
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({'counts':out['counts'],'matured_12h_metrics':out['matured_12h_metrics']}, sort_keys=True))


if __name__ == '__main__':
    main()
