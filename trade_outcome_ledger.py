"""Read-only outcome ledger for frozen ATLAS forward observations.

Official Production outcome semantics are fail-closed: a row is a Production
signal only when it carries the explicit canonical decision contract published
by Final Trade Guard. Legacy score-qualified rows remain available only through
an explicitly named research scope and are never backfilled or reclassified as
Production trades.
"""

HORIZONS = (4, 8, 12)
UNKNOWN_VERSION = 'UNKNOWN'
CANONICAL_SOURCE = 'FINAL_TRADE_GATE'
CANONICAL_SCHEMA = 'ATLAS_CANONICAL_DECISION_TRUTH_V1'


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _score(row):
    return _fnum(row.get('final_score')) if row.get('final_score') is not None else _fnum(row.get('champion_score'))


def _canonical(row):
    value = (row or {}).get('canonical_decision')
    return value if isinstance(value, dict) else {}


def is_production_signal(row):
    """True only for explicit Final Trade Gate canonical TRADE READY rows."""
    c = _canonical(row)
    direction = str(c.get('direction') or c.get('decision') or '').upper()
    decision_id = str(c.get('decision_id') or '').strip()
    horizons = c.get('evaluation_horizons_h')
    return bool(
        c.get('schema') == CANONICAL_SCHEMA
        and c.get('source_of_truth') == CANONICAL_SOURCE
        and c.get('canonical_source_present') is True
        and c.get('trade_ready') is True
        and c.get('paper_trade_eligible') is True
        and direction in ('LONG', 'SHORT')
        and decision_id
        and list(horizons or []) == list(HORIZONS)
    )


def is_legacy_score_signal(row):
    """Historical score/flag lane only; canonical rows are never duplicated here."""
    c = _canonical(row)
    if c.get('canonical_source_present') is True and c.get('source_of_truth') == CANONICAL_SOURCE:
        return False
    if 'production_signal_qualified' in (row or {}):
        return bool(row.get('production_signal_qualified'))
    score = _score(row or {})
    threshold = _fnum((row or {}).get('signal_threshold'))
    return bool(score is not None and threshold is not None and score >= threshold)


def is_research_champion(row):
    if 'research_champion_take' in row:
        return bool(row.get('research_champion_take'))
    return bool(row.get('champion_take'))


def _direction(row):
    if is_production_signal(row):
        c = _canonical(row)
        return str(c.get('direction') or c.get('decision') or '').upper()
    return str(row.get('direction') or '').upper()


def _directional_return(row, horizon):
    raw = _fnum((row.get('forward_return_pct') or {}).get(str(horizon)))
    if raw is None:
        return None, None
    direction = _direction(row)
    if direction == 'LONG':
        return raw, raw
    if direction == 'SHORT':
        return raw, -raw
    return raw, None


def classify_row(row, horizon=12):
    horizon = int(horizon)
    if horizon not in HORIZONS:
        raise ValueError('horizon must be one of 4, 8, 12')

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
    canonical = _canonical(row)
    return {
        'id': row.get('id'),
        'decision_id': canonical.get('decision_id') if production_qualified else None,
        'captured_at': row.get('captured_at'),
        'captured_at_ms': row.get('captured_at_ms'),
        'symbol': row.get('symbol'),
        'direction': _direction(row),
        'entry': _fnum(row.get('entry')),
        'score': _score(row),
        'signal_threshold': _fnum(row.get('signal_threshold')),
        'scoring_version': row.get('scoring_version'),
        'decision_version': row.get('decision_version'),
        'trade_plan_version': row.get('trade_plan_version'),
        'policy_version': row.get('policy_version'),
        'generation_id': row.get('generation_id'),
        'playbook': row.get('playbook_primary'),
        'source': row.get('auto_source'),
        'signal_qualified': production_qualified,
        'production_signal_qualified': production_qualified,
        'canonical_source_present': bool(canonical.get('canonical_source_present')),
        'canonical_source_of_truth': canonical.get('source_of_truth'),
        'canonical_schema': canonical.get('schema'),
        'research_champion': research_champion,
        'research_sampling_lane': bool(row.get('research_sampling_lane')),
        'legacy_score_signal': is_legacy_score_signal(row),
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


def build_ledger(rows, horizon=12, scope='signals', symbol=None, limit=200):
    scope = str(scope or 'signals').lower()
    if scope not in ('signals', 'legacy_score_signals', 'champions', 'all'):
        raise ValueError('scope must be signals, legacy_score_signals, champions or all')
    symbol = str(symbol or '').upper() or None
    selected = []
    for row in rows or []:
        direction = _direction(row)
        if direction not in ('LONG', 'SHORT'):
            continue
        if scope == 'signals' and not is_production_signal(row):
            continue
        if scope == 'legacy_score_signals' and not is_legacy_score_signal(row):
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


def summarize(rows, horizon=12, scope='signals'):
    ledger = build_ledger(rows, horizon=horizon, scope=scope, limit=2000)
    by_symbol = {}
    by_direction = {}
    for item in ledger:
        by_symbol.setdefault(item.get('symbol') or 'UNKNOWN', []).append(item)
        by_direction.setdefault(item.get('direction') or 'UNKNOWN', []).append(item)
    return {
        'schema': 'ATLAS_TRADE_OUTCOME_SUMMARY_V3_CANONICAL_FINAL_GATE',
        'horizon_h': int(horizon),
        'evaluation_horizons_h': list(HORIZONS),
        'scope': scope,
        'scope_semantics': {
            'signals': 'Explicit FINAL_TRADE_GATE canonical TRADE READY only',
            'legacy_score_signals': 'Legacy score/flag-qualified research rows only; canonical rows excluded; never official Production trades',
            'champions': 'Broader research champion lane',
            'all': 'All directional forward observations',
        },
        'canonical_source_of_truth': CANONICAL_SOURCE if scope == 'signals' else None,
        'legacy_backfill_allowed': False,
        'overall': _bucket(ledger),
        'by_symbol': {k: _bucket(v) for k, v in sorted(by_symbol.items())},
        'by_direction': {k: _bucket(v) for k, v in sorted(by_direction.items())},
        'by_scoring_version': _version_buckets(ledger, 'scoring_version'),
        'by_decision_version': _version_buckets(ledger, 'decision_version'),
        'by_trade_plan_version': _version_buckets(ledger, 'trade_plan_version'),
        'version_cohort_methodology': 'Cohorts use only frozen provenance. Missing legacy provenance is grouped under UNKNOWN and is never inferred.',
        'methodology': 'Official signals require explicit FINAL_TRADE_GATE canonical TRADE READY proof. WIN/LOSS uses frozen forward return in that direction at 4h, 8h or 12h; no score fallback or retrospective reclassification.',
        'r_multiple_available': False,
        'research_only': True,
        'live_execution': False,
    }
