"""Read-only outcome ledger for frozen ATLAS forward observations.

This module never changes scores, thresholds, signals, archives, or execution.
It classifies already-matured directional observations as WIN / LOSS / FLAT
using the canonical forward_return_pct captured by ATLAS.

Scope semantics:
- signals: strict Production-qualified observations only.
- champions: broader research champion lane (legacy champion_take=True).
- all: every directional forward observation.

Legacy rows that predate explicit production_signal_qualified are classified
using their frozen score and threshold when available, falling back to the
current historical Production threshold of 68.
"""

HORIZONS = (1, 4, 12, 24)
LEGACY_PRODUCTION_THRESHOLD = 68.0
UNKNOWN_VERSION = 'UNKNOWN'


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _score(row):
    return _fnum(row.get('final_score')) if row.get('final_score') is not None else _fnum(row.get('champion_score'))


def is_production_signal(row):
    if 'production_signal_qualified' in row:
        return bool(row.get('production_signal_qualified'))
    score = _score(row)
    threshold = _fnum(row.get('signal_threshold'))
    if threshold is None:
        threshold = LEGACY_PRODUCTION_THRESHOLD
    return bool(score is not None and score >= threshold)


def is_research_champion(row):
    if 'research_champion_take' in row:
        return bool(row.get('research_champion_take'))
    return bool(row.get('champion_take'))


def _directional_return(row, horizon):
    raw = _fnum((row.get('forward_return_pct') or {}).get(str(horizon)))
    if raw is None:
        return None, None
    direction = str(row.get('direction') or '').upper()
    if direction == 'LONG':
        return raw, raw
    if direction == 'SHORT':
        return raw, -raw
    return raw, None


def classify_row(row, horizon=24):
    horizon = int(horizon)
    if horizon not in HORIZONS:
        raise ValueError('horizon must be one of 1, 4, 12, 24')

    raw_return, directional_return = _directional_return(row, horizon)
    if directional_return is None:
        outcome = 'OPEN'
    elif directional_return > 0:
        outcome = 'WIN'
    elif directional_return < 0:
        outcome = 'LOSS'
    else:
        outcome = 'FLAT'

    production_qualified = is_production_signal(row)
    research_champion = is_research_champion(row)
    return {
        'id': row.get('id'),
        'captured_at': row.get('captured_at'),
        'captured_at_ms': row.get('captured_at_ms'),
        'symbol': row.get('symbol'),
        'direction': row.get('direction'),
        'entry': _fnum(row.get('entry')),
        'score': _score(row),
        'signal_threshold': _fnum(row.get('signal_threshold')) or LEGACY_PRODUCTION_THRESHOLD,
        'scoring_version': row.get('scoring_version'),
        'decision_version': row.get('decision_version'),
        'trade_plan_version': row.get('trade_plan_version'),
        'policy_version': row.get('policy_version'),
        'generation_id': row.get('generation_id'),
        'playbook': row.get('playbook_primary'),
        'source': row.get('auto_source'),
        'signal_qualified': production_qualified,
        'production_signal_qualified': production_qualified,
        'research_champion': research_champion,
        'research_sampling_lane': bool(row.get('research_sampling_lane')),
        'horizon_h': horizon,
        'market_return_pct': raw_return,
        'directional_return_pct': directional_return,
        'outcome': outcome,
        'rr_tp1': _fnum(row.get('rr_tp1')),
        'rr_tp2': _fnum(row.get('rr_tp2')),
        'r_multiple': None,
        'r_multiple_status': 'UNAVAILABLE_WITHOUT_FROZEN_STOP_DISTANCE',
        'research_only': True,
        'live_execution': False,
    }


def build_ledger(rows, horizon=24, scope='signals', symbol=None, limit=200):
    scope = str(scope or 'signals').lower()
    if scope not in ('signals', 'champions', 'all'):
        raise ValueError('scope must be signals, champions or all')
    symbol = str(symbol or '').upper() or None
    selected = []
    for row in rows or []:
        if str(row.get('direction') or '').upper() not in ('LONG', 'SHORT'):
            continue
        if scope == 'signals' and not is_production_signal(row):
            continue
        if scope == 'champions' and not is_research_champion(row):
            continue
        if symbol and str(row.get('symbol') or '').upper() != symbol:
            continue
        selected.append(classify_row(row, horizon))
    selected.sort(key=lambda x: int(x.get('captured_at_ms') or 0), reverse=True)
    return selected[:max(1, min(2000, int(limit or 200)))]


def _bucket(rows):
    wins = [x for x in rows if x['outcome'] == 'WIN']
    losses = [x for x in rows if x['outcome'] == 'LOSS']
    flats = [x for x in rows if x['outcome'] == 'FLAT']
    opens = [x for x in rows if x['outcome'] == 'OPEN']
    closed = wins + losses + flats
    decisive = wins + losses
    avg = None
    if decisive:
        avg = round(sum(float(x['directional_return_pct']) for x in decisive) / len(decisive), 6)
    return {
        'total': len(rows),
        'closed': len(closed),
        'open': len(opens),
        'wins': len(wins),
        'losses': len(losses),
        'flat': len(flats),
        'win_rate_pct': round(100 * len(wins) / len(decisive), 2) if decisive else None,
        'average_directional_return_pct': avg,
    }


def _version_buckets(ledger, field):
    grouped = {}
    for item in ledger:
        key = str(item.get(field) or UNKNOWN_VERSION)
        grouped.setdefault(key, []).append(item)
    return {key: _bucket(rows) for key, rows in sorted(grouped.items())}


def summarize(rows, horizon=24, scope='signals'):
    ledger = build_ledger(rows, horizon=horizon, scope=scope, limit=2000)
    by_symbol = {}
    by_direction = {}
    for item in ledger:
        by_symbol.setdefault(item.get('symbol') or 'UNKNOWN', []).append(item)
        by_direction.setdefault(item.get('direction') or 'UNKNOWN', []).append(item)
    return {
        'schema': 'ATLAS_TRADE_OUTCOME_SUMMARY_V2_VERSION_COHORTS',
        'horizon_h': int(horizon),
        'scope': scope,
        'scope_semantics': {
            'signals': 'Production-qualified only',
            'champions': 'Broader research champion lane',
            'all': 'All directional forward observations',
        },
        'overall': _bucket(ledger),
        'by_symbol': {k: _bucket(v) for k, v in sorted(by_symbol.items())},
        'by_direction': {k: _bucket(v) for k, v in sorted(by_direction.items())},
        'by_scoring_version': _version_buckets(ledger, 'scoring_version'),
        'by_decision_version': _version_buckets(ledger, 'decision_version'),
        'by_trade_plan_version': _version_buckets(ledger, 'trade_plan_version'),
        'version_cohort_methodology': 'Cohorts are computed only from frozen observation provenance; missing legacy provenance is grouped under UNKNOWN and never inferred.',
        'methodology': 'WIN/LOSS is based on frozen canonical forward return in the signaled direction at the selected horizon. It is not TP/SL path settlement.',
        'r_multiple_available': False,
        'research_only': True,
        'live_execution': False,
    }
