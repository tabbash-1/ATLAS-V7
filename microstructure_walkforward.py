"""ATLAS Microstructure Memory prequential A/B evaluator.

Uses only microstructure evidence frozen at signal time and later canonical TP/SL
settlements. It does NOT turn microstructure into a trading gate. The purpose is
to measure whether flow alignment or crowding/opposition adds incremental edge
before any Production rule is changed.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = 'MICROSTRUCTURE_WALKFORWARD_V1_OBSERVE_ONLY'
MIN_ALIGNED_SETTLED = 15
MIN_OPPOSED_SETTLED = 10
FOLD_SIZE = 20


def read_observations(path):
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get('schema') != 'ATLAS_MICROSTRUCTURE_OBSERVATION_V1':
                continue
            if row.get('production_signal_qualified') is not True:
                continue
            if row.get('research_sample') is True or not row.get('forward_id'):
                continue
            out.append(row)
    out.sort(key=lambda x: int(x.get('forward_captured_at_ms') or 0))
    return out


def classify_relation(direction, consensus):
    direction = str(direction or '').upper()
    consensus = str(consensus or 'INSUFFICIENT').upper()
    if direction == 'LONG':
        if consensus == 'BULLISH_FLOW':
            return 'ALIGNED'
        if consensus in ('BEARISH_FLOW', 'LONG_CROWDING_RISK'):
            return 'OPPOSED_OR_CROWDED'
    elif direction == 'SHORT':
        if consensus == 'BEARISH_FLOW':
            return 'ALIGNED'
        if consensus in ('BULLISH_FLOW', 'SHORT_CROWDING_RISK'):
            return 'OPPOSED_OR_CROWDED'
    return 'MIXED_OR_INSUFFICIENT'


def _metrics(rows):
    rs = [float(x['r_multiple']) for x in rows if x.get('r_multiple') is not None]
    wins = sum(1 for x in rows if x.get('path_outcome') == 'WIN_TP2')
    losses = sum(1 for x in rows if x.get('path_outcome') == 'LOSS')
    gross_win = sum(x for x in rs if x > 0)
    gross_loss = -sum(x for x in rs if x < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else None)
    return {
        'n': len(rows),
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(wins / (wins + losses) * 100, 2) if wins + losses else None,
        'net_r': round(sum(rs), 6),
        'average_r': round(sum(rs) / len(rs), 6) if rs else None,
        'profit_factor': round(pf, 4) if pf is not None else None,
    }


def join(observations, settlements):
    by_id = {str(x.get('id')): x for x in settlements or [] if x.get('id')}
    out = []
    for obs in observations or []:
        sid = str(obs.get('forward_id') or '')
        settle = by_id.get(sid)
        if not settle or settle.get('r_multiple') is None:
            continue
        context = obs.get('microstructure_memory') or {}
        consensus = context.get('consensus') or 'INSUFFICIENT'
        out.append({
            'forward_id': sid,
            'captured_at_ms': int(obs.get('forward_captured_at_ms') or 0),
            'symbol': obs.get('symbol'),
            'direction': obs.get('direction'),
            'consensus': consensus,
            'ready_windows': int(context.get('ready_windows') or 0),
            'relation': classify_relation(obs.get('direction'), consensus),
            'path_outcome': settle.get('path_outcome'),
            'r_multiple': settle.get('r_multiple'),
        })
    out.sort(key=lambda x: x['captured_at_ms'])
    return out


def _folds(rows):
    folds = []
    for start in range(0, len(rows), FOLD_SIZE):
        chunk = rows[start:start + FOLD_SIZE]
        if not chunk:
            continue
        aligned = [x for x in chunk if x['relation'] == 'ALIGNED']
        opposed = [x for x in chunk if x['relation'] == 'OPPOSED_OR_CROWDED']
        folds.append({
            'fold': len(folds) + 1,
            'start_ms': chunk[0]['captured_at_ms'],
            'end_ms': chunk[-1]['captured_at_ms'],
            'baseline': _metrics(chunk),
            'aligned': _metrics(aligned),
            'opposed_or_crowded': _metrics(opposed),
        })
    return folds


def report(observations, settlements):
    clean = [x for x in observations or [] if x.get('production_signal_qualified') is True and x.get('research_sample') is not True]
    joined = join(clean, settlements)
    aligned = [x for x in joined if x['relation'] == 'ALIGNED']
    opposed = [x for x in joined if x['relation'] == 'OPPOSED_OR_CROWDED']
    mixed = [x for x in joined if x['relation'] == 'MIXED_OR_INSUFFICIENT']
    baseline = _metrics(joined)
    aligned_m = _metrics(aligned)
    opposed_m = _metrics(opposed)
    mixed_m = _metrics(mixed)

    blockers = []
    if len(aligned) < MIN_ALIGNED_SETTLED:
        blockers.append('INSUFFICIENT_ALIGNED_SETTLED')
    if len(opposed) < MIN_OPPOSED_SETTLED:
        blockers.append('INSUFFICIENT_OPPOSED_SETTLED')

    aligned_delta = None
    opposed_delta = None
    if aligned_m['average_r'] is not None and baseline['average_r'] is not None:
        aligned_delta = aligned_m['average_r'] - baseline['average_r']
    if opposed_m['average_r'] is not None and baseline['average_r'] is not None:
        opposed_delta = opposed_m['average_r'] - baseline['average_r']

    folds = _folds(joined)
    informative_folds = [f for f in folds if f['aligned']['n'] >= 3 and f['opposed_or_crowded']['n'] >= 2]
    aligned_better_folds = sum(
        1 for f in informative_folds
        if f['aligned']['average_r'] is not None
        and f['opposed_or_crowded']['average_r'] is not None
        and f['aligned']['average_r'] > f['opposed_or_crowded']['average_r']
    )

    evidence_supports_future_gate = bool(
        not blockers
        and aligned_delta is not None and aligned_delta > 0
        and opposed_delta is not None and opposed_delta < 0
        and len(informative_folds) >= 3
        and aligned_better_folds >= 2
    )

    return {
        'version': VERSION,
        'status': 'VALIDATION_READ_AVAILABLE' if not blockers else 'COLLECTING',
        'evidence_supports_future_gate': evidence_supports_future_gate,
        'gate_promoted': False,
        'gate_mode': 'OBSERVE_ONLY_UNTIL_WALK_FORWARD_VALIDATED',
        'blockers': blockers,
        'frozen_observations': len(clean),
        'settled_joined': len(joined),
        'baseline': baseline,
        'aligned': aligned_m,
        'opposed_or_crowded': opposed_m,
        'mixed_or_insufficient': mixed_m,
        'aligned_average_r_delta_vs_baseline': round(aligned_delta, 6) if aligned_delta is not None else None,
        'opposed_average_r_delta_vs_baseline': round(opposed_delta, 6) if opposed_delta is not None else None,
        'walk_forward_folds': folds,
        'informative_folds': len(informative_folds),
        'folds_where_aligned_beats_opposed': aligned_better_folds,
        'method': 'FROZEN_AT_SIGNAL_MICROSTRUCTURE_THEN_LATER_CANONICAL_TP_SL_SETTLEMENT',
        'hindsight_recomputation_allowed': False,
        'research_samples_included': False,
        'shadow_only': True,
        'can_override_production': False,
        'live_execution': False,
    }
