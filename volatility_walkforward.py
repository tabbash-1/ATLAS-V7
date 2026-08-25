"""ATLAS volatility-geometry prequential walk-forward validator.

Reads only volatility forecasts frozen at the instant of an explicit Production-
qualified Forward observation, then joins them later to canonical TP/SL path
settlements by forward_id. Each 1h/4h/12h geometry view is evaluated separately;
this module never assumes which horizon the trade belongs to and never promotes a
Production gate.
"""

from __future__ import annotations

import json
from pathlib import Path

VERSION = 'VOLATILITY_WALKFORWARD_V1_MULTI_HORIZON_PREQUENTIAL'
HORIZONS = ('1', '4', '12')
MIN_SETTLED_FOR_READ = 30
MIN_CATEGORY_FOR_READ = 10
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
            if row.get('schema') != 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1':
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
    equity = peak = max_dd = 0.0
    for value in rs:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        'n': len(rs),
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(wins / (wins + losses) * 100, 2) if wins + losses else None,
        'net_r': round(net_r, 6),
        'average_r': round(net_r / len(rs), 6) if rs else None,
        'profit_factor': round(pf, 4) if pf is not None else None,
        'max_drawdown_r': round(max_dd, 6) if rs else None,
    }


def classify_geometry(fit):
    fit = fit or {}
    if fit.get('status') != 'READY':
        return 'INSUFFICIENT'
    target = str(fit.get('target_fit') or '')
    stop = str(fit.get('stop_fit') or '')
    if target == 'PLAUSIBLE_VS_EMPIRICAL_P80' and stop == 'PLAUSIBLE_VS_EMPIRICAL_P80':
        return 'PLAUSIBLE_BOTH'
    risks = []
    if target == 'STRETCHED_VS_EMPIRICAL_P80':
        risks.append('STRETCHED_TARGET')
    if stop == 'TIGHT_VS_EMPIRICAL_P80':
        risks.append('TIGHT_STOP')
    if risks:
        return '+'.join(risks)
    return 'OTHER_READY'


def join(observations, settlements):
    by_id = {str(x.get('id')): x for x in settlements or [] if x.get('id')}
    out = []
    for obs in observations or []:
        sid = str(obs.get('forward_id') or '')
        settle = by_id.get(sid)
        if not settle or settle.get('r_multiple') is None:
            continue
        fits = obs.get('geometry_fit_by_horizon') or {}
        horizon_views = {}
        for h in HORIZONS:
            fit = fits.get(h) or {}
            horizon_views[h] = {
                'category': classify_geometry(fit),
                'target_fit': fit.get('target_fit'),
                'stop_fit': fit.get('stop_fit'),
                'target_to_p80_ratio': fit.get('target_to_p80_ratio'),
                'stop_to_p80_ratio': fit.get('stop_to_p80_ratio'),
            }
        out.append({
            'forward_id': sid,
            'captured_at_ms': int(obs.get('forward_captured_at_ms') or 0),
            'symbol': obs.get('symbol'),
            'direction': obs.get('direction'),
            'volatility_regime': (obs.get('forecast') or {}).get('volatility_regime'),
            'horizon_views': horizon_views,
            'path_outcome': settle.get('path_outcome'),
            'r_multiple': settle.get('r_multiple'),
        })
    out.sort(key=lambda x: x['captured_at_ms'])
    return out


def _fold_evidence(rows, horizon):
    folds = []
    for start in range(0, len(rows), FOLD_SIZE):
        chunk = rows[start:start + FOLD_SIZE]
        if not chunk:
            continue
        plausible = [x for x in chunk if x['horizon_views'][horizon]['category'] == 'PLAUSIBLE_BOTH']
        risky = [x for x in chunk if x['horizon_views'][horizon]['category'] in (
            'STRETCHED_TARGET', 'TIGHT_STOP', 'STRETCHED_TARGET+TIGHT_STOP'
        )]
        folds.append({
            'fold': len(folds) + 1,
            'start_ms': chunk[0]['captured_at_ms'],
            'end_ms': chunk[-1]['captured_at_ms'],
            'baseline': _metrics(chunk),
            'plausible_both': _metrics(plausible),
            'risky_geometry': _metrics(risky),
        })
    informative = [f for f in folds if f['plausible_both']['n'] >= 5 and f['risky_geometry']['n'] >= 5]
    plausible_beats = sum(
        1 for f in informative
        if f['plausible_both']['average_r'] is not None
        and f['risky_geometry']['average_r'] is not None
        and f['plausible_both']['average_r'] > f['risky_geometry']['average_r']
    )
    return folds, informative, plausible_beats


def _horizon_report(rows, horizon):
    base = _metrics(rows)
    categories = {}
    for category in ('PLAUSIBLE_BOTH', 'STRETCHED_TARGET', 'TIGHT_STOP', 'STRETCHED_TARGET+TIGHT_STOP', 'OTHER_READY', 'INSUFFICIENT'):
        subset = [x for x in rows if x['horizon_views'][horizon]['category'] == category]
        categories[category] = _metrics(subset)

    plausible = categories['PLAUSIBLE_BOTH']
    risky_rows = [x for x in rows if x['horizon_views'][horizon]['category'] in (
        'STRETCHED_TARGET', 'TIGHT_STOP', 'STRETCHED_TARGET+TIGHT_STOP'
    )]
    risky = _metrics(risky_rows)
    folds, informative, plausible_beats = _fold_evidence(rows, horizon)

    p_delta = None
    r_delta = None
    if plausible['average_r'] is not None and base['average_r'] is not None:
        p_delta = plausible['average_r'] - base['average_r']
    if risky['average_r'] is not None and base['average_r'] is not None:
        r_delta = risky['average_r'] - base['average_r']

    blockers = []
    if base['n'] < MIN_SETTLED_FOR_READ:
        blockers.append('INSUFFICIENT_SETTLED_FROZEN_OBSERVATIONS')
    if plausible['n'] < MIN_CATEGORY_FOR_READ:
        blockers.append('INSUFFICIENT_PLAUSIBLE_GEOMETRY_SETTLED')
    if risky['n'] < MIN_CATEGORY_FOR_READ:
        blockers.append('INSUFFICIENT_RISKY_GEOMETRY_SETTLED')
    if len(informative) < 3:
        blockers.append('INSUFFICIENT_INFORMATIVE_FOLDS')
    elif plausible_beats < 2:
        blockers.append('NO_STABLE_GEOMETRY_EXPECTANCY_SEPARATION')

    evidence = bool(
        not blockers
        and p_delta is not None and p_delta > 0
        and r_delta is not None and r_delta < 0
        and plausible_beats >= 2
    )
    return {
        'horizon_h': int(horizon),
        'status': 'VALIDATION_READ_AVAILABLE' if not blockers else 'COLLECTING',
        'evidence_supports_future_geometry_filter': evidence,
        'blockers': blockers,
        'baseline': base,
        'categories': categories,
        'risky_geometry_combined': risky,
        'plausible_average_r_delta_vs_baseline': round(p_delta, 6) if p_delta is not None else None,
        'risky_average_r_delta_vs_baseline': round(r_delta, 6) if r_delta is not None else None,
        'walk_forward_folds': folds,
        'informative_folds': len(informative),
        'folds_where_plausible_beats_risky': plausible_beats,
        'gate_promoted': False,
        'can_override_production': False,
    }


def report(observations, settlements):
    clean = [x for x in observations or [] if x.get('production_signal_qualified') is True and x.get('research_sample') is not True]
    clean.sort(key=lambda x: int(x.get('forward_captured_at_ms') or 0))
    joined = join(clean, settlements)
    by_horizon = {h: _horizon_report(joined, h) for h in HORIZONS}
    supported = [int(h) for h, row in by_horizon.items() if row['evidence_supports_future_geometry_filter']]
    return {
        'version': VERSION,
        'status': 'VALIDATION_READ_AVAILABLE' if any(row['status'] == 'VALIDATION_READ_AVAILABLE' for row in by_horizon.values()) else 'COLLECTING',
        'frozen_observations': len(clean),
        'settled_joined': len(joined),
        'by_horizon': by_horizon,
        'horizons_supporting_future_filter': supported,
        'chosen_trade_horizon_assumed': False,
        'method': 'PREQUENTIAL_FROZEN_VOLATILITY_GEOMETRY_THEN_LATER_CANONICAL_TP_SL_SETTLEMENT',
        'hindsight_recomputation_allowed': False,
        'research_samples_included': False,
        'gate_promoted': False,
        'gate_mode': 'OBSERVE_ONLY',
        'can_override_production': False,
        'live_execution': False,
    }
