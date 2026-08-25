"""ATLAS WAIT diagnostics.

Analyzes settled opportunity-cost records produced from Production WAIT snapshots.
This layer is descriptive only: it identifies which blockers are associated with
missed directional moves, but never changes score thresholds or execution rules.
"""

VERSION = 'WAIT_DIAGNOSTICS_V1'
HORIZONS = (1, 3, 6, 12, 24)
MIN_REVIEW_SAMPLE = 10
MATERIAL_DIRECTIONAL_MOVE_PCT = 1.0
MATERIAL_UNSIGNED_MOVE_PCT = 2.0


def _f(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _horizon(row, hours):
    return (row.get('horizons') or {}).get(f'{int(hours)}h') or {}


def score_band(score, threshold=68.0):
    s = _f(score); t = _f(threshold, 68.0)
    if s is None: return 'NO_SCORE'
    if s < 50: return '<50'
    if s < 60: return '50-59'
    if s < t: return f'60-{int(t)-1}'
    if s < 75: return f'{int(t)}-74'
    if s < 82: return '75-81'
    return '82+'


def blocker(row):
    reason = str(row.get('reason') or 'UNKNOWN')
    attr = row.get('score_attribution') or {}
    obstacle = _f(attr.get('obstacle_adjustment'), 0) or 0
    futures = _f(attr.get('futures_adjustment'), 0) or 0
    rel = _f(attr.get('relative_strength_adjustment'), 0) or 0
    if reason == 'NO_DIRECTIONAL_CONSENSUS': return 'NO_DIRECTIONAL_CONSENSUS'
    if obstacle <= -4: return 'STRUCTURE_OBSTACLE_PENALTY'
    if futures < 0: return 'FUTURES_OPPOSITION'
    if rel < 0: return 'RELATIVE_STRENGTH_OPPOSITION'
    if reason == 'SCORE_BELOW_SIGNAL_THRESHOLD': return 'SCORE_GAP_OTHER'
    return reason


def classify(row, hours=24):
    h = _horizon(row, hours)
    direction = str(row.get('candidate_direction') or 'NONE').upper()
    directional = _f(h.get('directional_return_pct'))
    raw = _f(h.get('change_pct'))
    if direction in ('LONG', 'SHORT') and directional is not None:
        if directional >= MATERIAL_DIRECTIONAL_MOVE_PCT:
            return 'MISSED_DIRECTIONAL_OPPORTUNITY'
        if directional <= -MATERIAL_DIRECTIONAL_MOVE_PCT:
            return 'WAIT_PROTECTED_CAPITAL'
        return 'MIXED_SMALL_MOVE'
    if raw is not None and abs(raw) >= MATERIAL_UNSIGNED_MOVE_PCT:
        return 'MATERIAL_MOVE_WITHOUT_CONSENSUS'
    if raw is not None:
        return 'NO_CONSENSUS_SMALL_MOVE'
    return 'UNSETTLED'


def _stats(rows, hours):
    labels = {}
    directional = []
    raw_moves = []
    for row in rows:
        label = classify(row, hours); labels[label] = labels.get(label, 0) + 1
        h = _horizon(row, hours)
        dr = _f(h.get('directional_return_pct')); raw = _f(h.get('change_pct'))
        if dr is not None: directional.append(dr)
        if raw is not None: raw_moves.append(raw)
    decisive = labels.get('MISSED_DIRECTIONAL_OPPORTUNITY', 0) + labels.get('WAIT_PROTECTED_CAPITAL', 0)
    return {
        'total': len(rows), 'settled': sum(1 for r in rows if classify(r, hours) != 'UNSETTLED'),
        'classification_counts': labels,
        'directional_decisive': decisive,
        'missed_directional_rate_pct': round(100 * labels.get('MISSED_DIRECTIONAL_OPPORTUNITY', 0) / decisive, 2) if decisive else None,
        'avg_directional_return_pct': round(sum(directional)/len(directional), 4) if directional else None,
        'avg_abs_market_move_pct': round(sum(abs(x) for x in raw_moves)/len(raw_moves), 4) if raw_moves else None,
    }


def diagnose(payload, hours=24):
    hours = int(hours)
    if hours not in HORIZONS: raise ValueError('hours must be one of 1,3,6,12,24')
    records = payload.get('records') if isinstance(payload, dict) else payload
    records = [r for r in (records or []) if isinstance(r, dict)]
    by_reason = {}; by_blocker = {}; by_band = {}; by_symbol = {}
    for r in records:
        by_reason.setdefault(str(r.get('reason') or 'UNKNOWN'), []).append(r)
        by_blocker.setdefault(blocker(r), []).append(r)
        by_band.setdefault(score_band(r.get('score'), r.get('threshold', 68)), []).append(r)
        by_symbol.setdefault(str(r.get('symbol') or 'UNKNOWN'), []).append(r)

    blocker_rows = {k: _stats(v, hours) for k,v in by_blocker.items()}
    review = []
    for name, st in blocker_rows.items():
        missed = st['classification_counts'].get('MISSED_DIRECTIONAL_OPPORTUNITY', 0)
        protected = st['classification_counts'].get('WAIT_PROTECTED_CAPITAL', 0)
        sample = missed + protected
        if sample >= MIN_REVIEW_SAMPLE:
            review.append({
                'blocker': name, 'decisive_sample': sample,
                'missed': missed, 'protected': protected,
                'missed_rate_pct': round(100*missed/sample,2),
                'review_priority': 'HIGH' if missed/sample >= .65 else 'MEDIUM' if missed/sample >= .50 else 'LOW',
            })
    review.sort(key=lambda x: (x['review_priority']=='HIGH', x['missed_rate_pct'], x['decisive_sample']), reverse=True)

    return {
        'schema': 'ATLAS_WAIT_DIAGNOSTICS_V1', 'version': VERSION, 'horizon_h': hours,
        'records': len(records), 'overall': _stats(records, hours),
        'by_reason': {k:_stats(v,hours) for k,v in sorted(by_reason.items())},
        'by_blocker': blocker_rows,
        'by_score_band': {k:_stats(v,hours) for k,v in by_band.items()},
        'by_symbol': {k:_stats(v,hours) for k,v in sorted(by_symbol.items())},
        'blocker_review': review,
        'definitions': {
            'missed_directional_opportunity': f'candidate direction gained >= {MATERIAL_DIRECTIONAL_MOVE_PCT}% by horizon',
            'wait_protected_capital': f'candidate direction lost >= {MATERIAL_DIRECTIONAL_MOVE_PCT}% by horizon',
            'material_move_without_consensus': f'no candidate direction and absolute market move >= {MATERIAL_UNSIGNED_MOVE_PCT}%; hindsight only, not a missed signal',
        },
        'safety': {'research_only': True, 'threshold_changed': False, 'execution_rules_changed': False},
    }
