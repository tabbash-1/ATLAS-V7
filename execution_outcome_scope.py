"""Strict canonical execution-qualified classification for ATLAS outcomes.

Official execution/outcome analytics start only from an explicit canonical
FINAL_TRADE_GATE TRADE READY row, then require valid frozen geometry. Historical
score-qualified flags are not an execution authority and are never backfilled.
"""

import trade_outcome_ledger

MIN_EXECUTION_RR = 1.0


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def geometry_integrity(geometry):
    g = geometry or {}
    direction = str(g.get('direction') or '').upper()
    entry = _fnum(g.get('entry'))
    stop = _fnum(g.get('stop_loss'))
    tp1 = _fnum(g.get('tp1'))
    tp2 = _fnum(g.get('tp2'))
    rr2 = _fnum(g.get('rr_tp2'))
    reasons = []

    if direction not in ('LONG', 'SHORT'):
        reasons.append('INVALID_DIRECTION')
    if any(v is None or v <= 0 for v in (entry, stop, tp1, tp2)):
        reasons.append('MISSING_OR_NONPOSITIVE_LEVEL')
    if rr2 is None:
        reasons.append('RR_UNAVAILABLE')
    elif rr2 < MIN_EXECUTION_RR:
        reasons.append('RR_BELOW_ONE_TO_ONE')

    if not reasons or all(r not in reasons for r in ('INVALID_DIRECTION', 'MISSING_OR_NONPOSITIVE_LEVEL')):
        if None not in (entry, stop, tp1, tp2):
            if direction == 'LONG' and not (stop < entry < tp1 <= tp2):
                reasons.append('INVALID_LONG_LEVEL_ORDER')
            elif direction == 'SHORT' and not (tp2 <= tp1 < entry < stop):
                reasons.append('INVALID_SHORT_LEVEL_ORDER')

    return {
        'valid': not reasons,
        'reasons': reasons,
        'min_rr': MIN_EXECUTION_RR,
        'rr_tp2': rr2,
        'direction': direction or None,
    }


def classify(row, geometry_record=None):
    row = row or {}
    geometry = (geometry_record or {}).get('geometry') if isinstance(geometry_record, dict) else None
    canonical_trade_ready = trade_outcome_ledger.is_production_signal(row)
    integrity = geometry_integrity(geometry)

    explicit_execution_ready = row.get('execution_ready') if 'execution_ready' in row else None
    explicit_trade_plan_status = row.get('trade_plan_status')
    explicit_block = explicit_execution_ready is False or explicit_trade_plan_status == 'SCORE_QUALIFIED_GEOMETRY_BLOCKED'

    qualified = bool(canonical_trade_ready and integrity['valid'] and not explicit_block)
    reasons = []
    if not canonical_trade_ready:
        reasons.append('NOT_CANONICAL_TRADE_READY')
    reasons.extend(integrity['reasons'])
    if explicit_execution_ready is False:
        reasons.append('EXPLICIT_EXECUTION_NOT_READY')
    if explicit_trade_plan_status == 'SCORE_QUALIFIED_GEOMETRY_BLOCKED':
        reasons.append('TRADE_PLAN_GEOMETRY_BLOCKED')

    return {
        'execution_qualified': qualified,
        'canonical_trade_ready': canonical_trade_ready,
        # Compatibility field; semantics are now canonical Final Gate, not score qualification.
        'production_signal_qualified': canonical_trade_ready,
        'decision_source_of_truth': 'FINAL_TRADE_GATE' if canonical_trade_ready else None,
        'geometry_integrity': integrity,
        'explicit_execution_ready': explicit_execution_ready,
        'trade_plan_status': explicit_trade_plan_status,
        'reasons': reasons,
    }


def filter_execution_rows(rows, geometry_map, symbol=None):
    symbol = str(symbol or '').upper() or None
    selected = []
    rejected = []
    for row in rows or []:
        direction = str(((row.get('canonical_decision') or {}).get('direction') or row.get('direction') or '')).upper()
        if direction not in ('LONG', 'SHORT'):
            continue
        if symbol and str(row.get('symbol') or '').upper() != symbol:
            continue
        rec = geometry_map.get(str(row.get('id') or ''))
        result = classify(row, rec)
        if result['execution_qualified']:
            selected.append(row)
        elif result['canonical_trade_ready']:
            rejected.append({'id': row.get('id'), 'symbol': row.get('symbol'), 'direction': direction, 'score': row.get('final_score') if row.get('final_score') is not None else row.get('champion_score'), **result})
    return selected, rejected


def annotate_settled_item(item):
    item = dict(item or {})
    result = geometry_integrity(item.get('geometry'))
    canonical = bool(item.get('canonical_trade_ready'))
    item['geometry_integrity'] = result
    item['execution_qualified'] = bool(canonical and result['valid'])
    return item


def rejection_summary(rejected):
    counts = {}
    for row in rejected or []:
        for reason in row.get('reasons') or []:
            counts[reason] = counts.get(reason, 0) + 1
    return {
        'rejected_canonical_trade_ready_rows': len(rejected or []),
        'reason_counts': dict(sorted(counts.items())),
        'decision_source_of_truth': 'FINAL_TRADE_GATE',
        'legacy_backfill_allowed': False,
    }
