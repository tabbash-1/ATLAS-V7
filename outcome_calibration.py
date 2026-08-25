"""ATLAS outcome calibration engine.

Read-only research layer that measures how frozen directional observations
performed across score bands and opportunity maturity. It NEVER changes the
Production threshold. Promotion recommendations are emitted only when sample
and edge requirements are met and remain advisory/research-only.
"""

VERSION = 'OUTCOME_CALIBRATION_V1'
HORIZONS = (1, 4, 12, 24)
DEFAULT_THRESHOLD = 68.0
MIN_DECISIVE_PER_BAND = 12
MIN_THRESHOLD_SAMPLE = 30


def _f(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _score(row):
    return _f(row.get('final_score'), _f(row.get('champion_score')))


def directional_return(row, horizon):
    raw = _f((row.get('forward_return_pct') or {}).get(str(int(horizon))))
    if raw is None:
        return None
    d = str(row.get('direction') or '').upper()
    if d == 'LONG':
        return raw
    if d == 'SHORT':
        return -raw
    return None


def score_band(score, threshold=DEFAULT_THRESHOLD):
    s = _f(score)
    t = _f(threshold, DEFAULT_THRESHOLD)
    if s is None:
        return 'NO_SCORE'
    if s < 50:
        return '<50'
    if s < 60:
        return '50-59'
    if s < t:
        return f'60-{int(t)-1}'
    if s < 75:
        return f'{int(t)}-74'
    if s < 82:
        return '75-81'
    return '82+'


def opportunity_state(row, threshold=DEFAULT_THRESHOLD):
    d = str(row.get('direction') or '').upper()
    if d not in ('LONG', 'SHORT'):
        return 'NO_SETUP'
    qualified = row.get('production_signal_qualified')
    if qualified is None:
        s = _score(row)
        qualified = bool(s is not None and s >= _f(row.get('signal_threshold'), threshold))
    if not qualified:
        return 'WATCH'
    if row.get('execution_ready') is True:
        return 'ACTIONABLE'
    status = str(row.get('trade_plan_status') or row.get('opportunity_state') or '').upper()
    if status in ('ACTIONABLE', 'EXECUTION_READY'):
        return 'ACTIONABLE'
    return 'ARMED'


def _stats(items):
    vals = [x['return'] for x in items if x.get('return') is not None]
    wins = [x for x in vals if x > 0]
    losses = [x for x in vals if x < 0]
    flats = [x for x in vals if x == 0]
    if not vals:
        return {'total': len(items), 'decisive': 0, 'wins': 0, 'losses': 0, 'flat': 0,
                'win_rate_pct': None, 'avg_directional_return_pct': None,
                'median_directional_return_pct': None, 'expectancy_pct': None}
    ordered = sorted(vals)
    n = len(ordered)
    med = ordered[n//2] if n % 2 else (ordered[n//2-1] + ordered[n//2]) / 2
    decisive = len(wins) + len(losses)
    avg = sum(vals) / len(vals)
    return {
        'total': len(items), 'decisive': decisive, 'wins': len(wins), 'losses': len(losses), 'flat': len(flats),
        'win_rate_pct': round(100 * len(wins) / decisive, 2) if decisive else None,
        'avg_directional_return_pct': round(avg, 6),
        'median_directional_return_pct': round(med, 6),
        'expectancy_pct': round(avg, 6),
    }


def _threshold_view(obs, threshold):
    accepted = [x for x in obs if x['score'] is not None and x['score'] >= threshold]
    rejected = [x for x in obs if x['score'] is not None and x['score'] < threshold]
    return {'threshold': threshold, 'accepted': _stats(accepted), 'rejected': _stats(rejected)}


def calibrate(rows, horizon=24, current_threshold=DEFAULT_THRESHOLD):
    horizon = int(horizon)
    if horizon not in HORIZONS:
        raise ValueError('horizon must be one of 1, 4, 12, 24')
    threshold = _f(current_threshold, DEFAULT_THRESHOLD)
    obs = []
    for row in rows or []:
        d = str(row.get('direction') or '').upper()
        if d not in ('LONG', 'SHORT'):
            continue
        score = _score(row)
        ret = directional_return(row, horizon)
        if score is None:
            continue
        obs.append({
            'symbol': row.get('symbol'), 'direction': d, 'score': score, 'return': ret,
            'band': score_band(score, threshold), 'state': opportunity_state(row, threshold),
        })

    by_band = {}
    by_state = {}
    by_symbol = {}
    for x in obs:
        by_band.setdefault(x['band'], []).append(x)
        by_state.setdefault(x['state'], []).append(x)
        by_symbol.setdefault(x.get('symbol') or 'UNKNOWN', []).append(x)

    # Counterfactual threshold scan is deliberately narrow. It is evidence, not auto-tuning.
    candidates = sorted(set([60, 62, 64, 66, int(threshold), 70, 72, 75]))
    threshold_scan = [_threshold_view(obs, t) for t in candidates]
    current = next((x for x in threshold_scan if x['threshold'] == int(threshold)), _threshold_view(obs, threshold))

    eligible = [x for x in threshold_scan if x['accepted']['decisive'] >= MIN_THRESHOLD_SAMPLE]
    best = None
    if eligible:
        best = max(eligible, key=lambda x: (
            x['accepted']['expectancy_pct'] if x['accepted']['expectancy_pct'] is not None else -999,
            x['accepted']['win_rate_pct'] if x['accepted']['win_rate_pct'] is not None else -999,
            x['accepted']['decisive']))

    recommendation = 'KEEP_THRESHOLD_COLLECT_MORE_DATA'
    rationale = 'Insufficient decisive samples for threshold promotion/demotion.'
    if best is not None and current['accepted']['decisive'] >= MIN_THRESHOLD_SAMPLE:
        cur_exp = current['accepted']['expectancy_pct']
        best_exp = best['accepted']['expectancy_pct']
        if cur_exp is not None and best_exp is not None and best['threshold'] != int(threshold) and best_exp >= cur_exp + 0.15:
            recommendation = 'REVIEW_THRESHOLD_CANDIDATE'
            rationale = f"Threshold {best['threshold']} has >=0.15pp higher observed expectancy with sufficient sample. Manual validation required."
        else:
            recommendation = 'KEEP_CURRENT_THRESHOLD'
            rationale = 'No sufficiently sampled candidate improves observed expectancy by the promotion margin.'

    return {
        'schema': 'ATLAS_OUTCOME_CALIBRATION_V1', 'version': VERSION,
        'horizon_h': horizon, 'current_threshold': threshold,
        'observations': len(obs), 'matured_observations': sum(1 for x in obs if x['return'] is not None),
        'overall': _stats(obs),
        'by_score_band': {k: {**_stats(v), 'sample_sufficient': _stats(v)['decisive'] >= MIN_DECISIVE_PER_BAND} for k, v in by_band.items()},
        'by_opportunity_state': {k: _stats(v) for k, v in by_state.items()},
        'by_symbol': {k: _stats(v) for k, v in sorted(by_symbol.items())},
        'threshold_scan': threshold_scan,
        'recommendation': {
            'status': recommendation, 'rationale': rationale,
            'candidate_threshold': best['threshold'] if best else None,
            'minimum_decisive_sample': MIN_THRESHOLD_SAMPLE,
            'auto_apply': False,
        },
        'methodology': 'Directional frozen forward returns grouped by frozen score. Threshold scan is counterfactual research only and never changes Production.',
        'research_only': True, 'live_execution': False, 'threshold_changed': False,
    }
