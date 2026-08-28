"""Read-only Smart Money shadow classifier for ATLAS.

The classifier consumes already-frozen derivatives/microstructure evidence from
ATLAS forward observations. It does not change scoring, thresholds, signals,
trade plans, alerts, portfolio rules, or execution. Its only purpose is to build
an auditable shadow cohort that can later be compared with realized outcomes.
"""

SHADOW_VERSION = 'ATLAS_SMART_MONEY_SHADOW_V1'


def _num(value, default=None):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def classify(row):
    x = row or {}
    taker = _num(x.get('taker_ratio'))
    book = _num(x.get('orderbook_imbalance'))
    oi = _num(x.get('oi_change_pct'))
    funding = _num(x.get('funding_rate'))
    futures_valid = bool(x.get('futures_available') or x.get('futures_shadow_validated'))

    votes_long = 0
    votes_short = 0
    evidence = []

    if taker is not None:
        if taker >= 1.08:
            votes_long += 1
            evidence.append('TAKER_BUY_DOMINANT')
        elif taker <= 0.92:
            votes_short += 1
            evidence.append('TAKER_SELL_DOMINANT')

    if book is not None:
        if book >= 0.10:
            votes_long += 1
            evidence.append('BOOK_BID_IMBALANCE')
        elif book <= -0.10:
            votes_short += 1
            evidence.append('BOOK_ASK_IMBALANCE')

    # OI alone is not directional; combine it only with funding sign as a
    # crowd/leverage context signal. Mild funding is intentionally neutral.
    if oi is not None and funding is not None and oi >= 1.0:
        if funding <= -0.00015:
            votes_long += 1
            evidence.append('OI_RISING_NEGATIVE_FUNDING_CONTRARIAN_LONG')
        elif funding >= 0.00015:
            votes_short += 1
            evidence.append('OI_RISING_POSITIVE_FUNDING_CONTRARIAN_SHORT')

    if votes_long >= 2 and votes_long > votes_short:
        direction = 'LONG'
        strength = votes_long
    elif votes_short >= 2 and votes_short > votes_long:
        direction = 'SHORT'
        strength = votes_short
    else:
        direction = 'NEUTRAL'
        strength = max(votes_long, votes_short)

    return {
        'schema': 'ATLAS_SMART_MONEY_SHADOW_CLASSIFICATION_V1',
        'shadow_version': SHADOW_VERSION,
        'symbol': x.get('symbol'),
        'captured_at': x.get('captured_at'),
        'captured_at_ms': x.get('captured_at_ms'),
        'production_direction': x.get('direction'),
        'shadow_direction': direction,
        'shadow_strength': strength,
        'votes_long': votes_long,
        'votes_short': votes_short,
        'evidence': evidence,
        'futures_evidence_validated': futures_valid,
        'eligible_for_evaluation': bool(futures_valid and direction in ('LONG', 'SHORT')),
        'research_only': True,
        'production_changed': False,
        'live_execution': False,
    }


def evaluate(row, horizon=24):
    """Attach frozen forward-return outcome to a shadow direction."""
    c = classify(row)
    raw = _num((row.get('forward_return_pct') or {}).get(str(int(horizon))))
    directional = None
    outcome = 'OPEN'
    if raw is not None and c['shadow_direction'] == 'LONG':
        directional = raw
    elif raw is not None and c['shadow_direction'] == 'SHORT':
        directional = -raw

    if directional is not None:
        if directional > 0:
            outcome = 'WIN'
        elif directional < 0:
            outcome = 'LOSS'
        else:
            outcome = 'FLAT'

    production_direction = str(row.get('direction') or '').upper()
    agreement = None
    if c['shadow_direction'] in ('LONG', 'SHORT') and production_direction in ('LONG', 'SHORT'):
        agreement = c['shadow_direction'] == production_direction

    return {
        **c,
        'horizon_h': int(horizon),
        'market_return_pct': raw,
        'shadow_directional_return_pct': directional,
        'shadow_outcome': outcome,
        'agrees_with_production': agreement,
    }


def summarize(rows, horizon=24):
    items = [evaluate(x, horizon=horizon) for x in (rows or [])]
    eligible = [x for x in items if x['eligible_for_evaluation']]
    closed = [x for x in eligible if x['shadow_outcome'] in ('WIN', 'LOSS', 'FLAT')]
    decisive = [x for x in closed if x['shadow_outcome'] in ('WIN', 'LOSS')]
    wins = [x for x in decisive if x['shadow_outcome'] == 'WIN']
    aligned = [x for x in eligible if x['agrees_with_production'] is True]
    opposed = [x for x in eligible if x['agrees_with_production'] is False]
    returns = [x['shadow_directional_return_pct'] for x in decisive if x['shadow_directional_return_pct'] is not None]
    return {
        'schema': 'ATLAS_SMART_MONEY_SHADOW_SUMMARY_V1',
        'shadow_version': SHADOW_VERSION,
        'horizon_h': int(horizon),
        'total_rows': len(items),
        'eligible': len(eligible),
        'closed': len(closed),
        'decisive': len(decisive),
        'wins': len(wins),
        'losses': len(decisive) - len(wins),
        'win_rate_pct': round(100 * len(wins) / len(decisive), 2) if decisive else None,
        'average_directional_return_pct': round(sum(returns) / len(returns), 6) if returns else None,
        'aligned_with_production': len(aligned),
        'opposed_to_production': len(opposed),
        'research_only': True,
        'production_changed': False,
        'promotion_decision': 'NOT_AUTOMATED',
        'methodology': 'Shadow direction requires at least two aligned frozen microstructure/derivatives votes and validated futures evidence; it never changes Production.',
    }
