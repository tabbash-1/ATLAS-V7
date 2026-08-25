"""ATLAS Profit Engine prequential walk-forward validator.

Evaluation is intentionally based only on Profit Engine observations frozen at
signal time. It never recomputes old regimes, costs, calibration or expected
value using information learned later. Frozen observations are joined to the
canonical TP/SL path settlement by forward_id.

This is a shadow research validator. It cannot alter Production decisions.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = 'PROFIT_ENGINE_WALKFORWARD_V1_PREQUENTIAL'
MIN_SETTLED_FOR_READ = 30
MIN_PROFIT_READY_FOR_READ = 15
FOLD_SIZE = 20


def read_observations(path):
    path = Path(path)
    out = []
    if not path.exists():
        return out
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get('schema') != 'ATLAS_PROFIT_ENGINE_OBSERVATION_V1':
                continue
            if row.get('production_signal_qualified') is not True:
                continue
            if row.get('research_sample') is True:
                continue
            if not row.get('forward_id'):
                continue
            out.append(row)
    out.sort(key=lambda x: int(x.get('forward_captured_at_ms') or 0))
    return out


def _metrics(rows):
    rs = [float(x['r_multiple']) for x in rows if x.get('r_multiple') is not None]
    wins = sum(1 for x in rows if x.get('path_outcome') == 'WIN_TP2')
    losses = sum(1 for x in rows if x.get('path_outcome') == 'LOSS')
    net_r = sum(rs)
    gross_win = sum(x for x in rs if x > 0)
    gross_loss = -sum(x for x in rs if x < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else (999.0 if gross_win > 0 else None)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in rs:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        'n': len(rows),
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(wins / (wins + losses) * 100, 2) if wins + losses else None,
        'net_r': round(net_r, 6),
        'average_r': round(net_r / len(rs), 6) if rs else None,
        'profit_factor': round(pf, 4) if pf is not None else None,
        'max_drawdown_r': round(max_dd, 6) if rs else None,
    }


def join_frozen_to_settlements(observations, settlements):
    by_id = {str(x.get('id')): x for x in settlements or [] if x.get('id')}
    joined = []
    for obs in observations or []:
        sid = str(obs.get('forward_id') or '')
        settle = by_id.get(sid)
        if not settle:
            continue
        # Only outcomes with an actual R value are performance-comparable.
        # Ambiguous/open/market-data errors remain unresolved and are not forced.
        if settle.get('r_multiple') is None:
            continue
        joined.append({
            'forward_id': sid,
            'captured_at_ms': int(obs.get('forward_captured_at_ms') or 0),
            'symbol': obs.get('symbol'),
            'direction': obs.get('direction'),
            'profit_ready': bool((obs.get('profit_engine') or {}).get('profit_ready')),
            'profit_blockers': list((obs.get('profit_engine') or {}).get('blockers') or []),
            'frozen_net_expected_r': (obs.get('profit_engine') or {}).get('net_expected_r'),
            'frozen_p_win': ((obs.get('profit_engine') or {}).get('probability') or {}).get('p_win'),
            'frozen_calibration_samples': ((obs.get('profit_engine') or {}).get('probability') or {}).get('samples'),
            'frozen_asset_regime': ((obs.get('market_regime') or {}).get('asset_regime')),
            'frozen_btc_regime': ((obs.get('market_regime') or {}).get('btc_regime')),
            'frozen_execution_validated': bool((obs.get('execution_cost') or {}).get('validated')),
            'path_outcome': settle.get('path_outcome'),
            'r_multiple': settle.get('r_multiple'),
        })
    joined.sort(key=lambda x: x['captured_at_ms'])
    return joined


def _folds(rows, fold_size=FOLD_SIZE):
    out = []
    if fold_size <= 0:
        return out
    for start in range(0, len(rows), fold_size):
        chunk = rows[start:start + fold_size]
        if not chunk:
            continue
        ready = [x for x in chunk if x.get('profit_ready')]
        out.append({
            'fold': len(out) + 1,
            'start_ms': chunk[0].get('captured_at_ms'),
            'end_ms': chunk[-1].get('captured_at_ms'),
            'production': _metrics(chunk),
            'profit_ready': _metrics(ready),
            'profit_ready_fraction_pct': round(len(ready) / len(chunk) * 100, 2),
        })
    return out


def report(observations, settlements):
    clean_obs = [x for x in observations or [] if x.get('production_signal_qualified') is True and x.get('research_sample') is not True]
    clean_obs.sort(key=lambda x: int(x.get('forward_captured_at_ms') or 0))
    joined = join_frozen_to_settlements(clean_obs, settlements)
    ready = [x for x in joined if x.get('profit_ready')]
    base = _metrics(joined)
    filt = _metrics(ready)
    folds = _folds(joined)

    avg_delta = None
    dd_delta = None
    pf_delta = None
    if base.get('average_r') is not None and filt.get('average_r') is not None:
        avg_delta = filt['average_r'] - base['average_r']
    if base.get('max_drawdown_r') is not None and filt.get('max_drawdown_r') is not None:
        dd_delta = base['max_drawdown_r'] - filt['max_drawdown_r']
    if base.get('profit_factor') is not None and filt.get('profit_factor') is not None:
        pf_delta = filt['profit_factor'] - base['profit_factor']

    blockers = []
    if len(joined) < MIN_SETTLED_FOR_READ:
        blockers.append('INSUFFICIENT_SETTLED_FROZEN_OBSERVATIONS')
    if len(ready) < MIN_PROFIT_READY_FOR_READ:
        blockers.append('INSUFFICIENT_PROFIT_READY_SETTLED_OBSERVATIONS')

    stable_folds = [f for f in folds if f['profit_ready']['n'] >= 5]
    positive_fold_count = sum(
        1 for f in stable_folds
        if f['profit_ready'].get('average_r') is not None
        and f['production'].get('average_r') is not None
        and f['profit_ready']['average_r'] > f['production']['average_r']
    )
    if len(stable_folds) >= 3 and positive_fold_count < 2:
        blockers.append('NO_STABLE_WALK_FORWARD_IMPROVEMENT')

    status = 'COLLECTING' if blockers else 'VALIDATION_READ_AVAILABLE'
    improves = bool(
        not blockers
        and avg_delta is not None and avg_delta > 0
        and (dd_delta is None or dd_delta >= 0)
        and len(stable_folds) >= 3
        and positive_fold_count >= 2
    )

    return {
        'version': VERSION,
        'status': status,
        'improves_production_expectancy': improves,
        'blockers': blockers,
        'frozen_observations': len(clean_obs),
        'settled_joined': len(joined),
        'profit_ready_settled': len(ready),
        'production_baseline': base,
        'profit_ready_subset': filt,
        'delta_average_r': round(avg_delta, 6) if avg_delta is not None else None,
        'drawdown_improvement_r': round(dd_delta, 6) if dd_delta is not None else None,
        'profit_factor_delta': round(pf_delta, 4) if pf_delta is not None else None,
        'walk_forward_folds': folds,
        'stable_folds': len(stable_folds),
        'folds_with_expectancy_improvement': positive_fold_count,
        'method': 'PREQUENTIAL_FROZEN_AT_SIGNAL_EVIDENCE_THEN_LATER_TP_SL_SETTLEMENT',
        'hindsight_recomputation_allowed': False,
        'research_samples_included': False,
        'shadow_only': True,
        'can_override_production': False,
        'live_execution': False,
    }
