"""Read-only outcome ledger for frozen ATLAS forward observations.

This module never changes scores, thresholds, signals, archives, or execution.
It classifies already-matured directional observations as WIN / LOSS / FLAT
using the canonical forward_return_pct captured by ATLAS. By default the ledger
shows signal-qualified observations only (champion_take=True); research-only
samples are available explicitly with scope=all.
"""

HORIZONS = (1, 4, 12, 24)


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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

    return {
        'id': row.get('id'),
        'captured_at': row.get('captured_at'),
        'captured_at_ms': row.get('captured_at_ms'),
        'symbol': row.get('symbol'),
        'direction': row.get('direction'),
        'entry': _fnum(row.get('entry')),
        'score': _fnum(row.get('final_score')) if row.get('final_score') is not None else _fnum(row.get('champion_score')),
        'playbook': row.get('playbook_primary'),
        'source': row.get('auto_source'),
        'signal_qualified': bool(row.get('champion_take')),
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
    if scope not in ('signals', 'all'):
        raise ValueError('scope must be signals or all')
    symbol = str(symbol or '').upper() or None
    selected = []
    for row in rows or []:
        if str(row.get('direction') or '').upper() not in ('LONG', 'SHORT'):
            continue
        if scope == 'signals' and not bool(row.get('champion_take')):
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


def summarize(rows, horizon=24, scope='signals'):
    ledger = build_ledger(rows, horizon=horizon, scope=scope, limit=2000)
    by_symbol = {}
    by_direction = {}
    for item in ledger:
        by_symbol.setdefault(item.get('symbol') or 'UNKNOWN', []).append(item)
        by_direction.setdefault(item.get('direction') or 'UNKNOWN', []).append(item)
    return {
        'schema': 'ATLAS_TRADE_OUTCOME_SUMMARY_V1',
        'horizon_h': int(horizon),
        'scope': scope,
        'overall': _bucket(ledger),
        'by_symbol': {k: _bucket(v) for k, v in sorted(by_symbol.items())},
        'by_direction': {k: _bucket(v) for k, v in sorted(by_direction.items())},
        'methodology': 'WIN/LOSS is based on frozen canonical forward return in the signaled direction at the selected horizon. It is not TP/SL path settlement.',
        'r_multiple_available': False,
        'research_only': True,
        'live_execution': False,
    }
