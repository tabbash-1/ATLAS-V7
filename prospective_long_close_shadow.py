"""Prospective research-only structure-confirmation shadow.

Evaluates whether a continuation setup that is close to prior structure also has
a verified closed-candle break and hold. This layer NEVER mutates Production,
score, threshold, qualification, geometry, or live execution. It exists only to
collect prospective evidence before any production veto is considered.
"""
from __future__ import annotations

import urllib.parse

from prospective_fourth_vote_shadow import shadow_from_row as fourth_vote_shadow_from_row

VERSION = 'ATLAS_PROSPECTIVE_STRUCTURE_CONFIRMATION_SHADOW_V2'


def _f(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def _atr_from_klines(klines, period=14):
    rows = list(klines or [])
    if len(rows) < 2:
        return None
    trs = []
    for i in range(max(1, len(rows) - period), len(rows)):
        high = _f(rows[i].get('high'))
        low = _f(rows[i].get('low'))
        prev_close = _f(rows[i - 1].get('close'))
        if high is None or low is None or prev_close is None:
            continue
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(trs) / len(trs) if trs else None


def structure_confirmation_from_row(row, klines=None):
    row = row or {}
    direction = str(row.get('direction') or '')
    attr = row.get('score_attribution') or {}
    obstacle_reason = str(attr.get('obstacle_reason') or '')
    level = _f(row.get('structural_obstacle_price'))
    if level is None:
        level = _f(attr.get('structural_obstacle_price'))
    if level is None:
        level = _f(attr.get('obstacle_price'))

    relevant = bool(direction in ('LONG', 'SHORT') and obstacle_reason == 'CLOSE_PRIOR_STRUCTURE')
    result = {
        'version': VERSION,
        'relevant': relevant,
        'direction': direction,
        'obstacle_reason': obstacle_reason,
        'structure_level': level,
        'state': 'NOT_APPLICABLE' if not relevant else 'UNKNOWN_NO_MARKET_EVIDENCE',
        'closed_candle_close': None,
        'current_price': None,
        'confirmation_buffer': None,
        'closed_break_confirmed': False,
        'hold_confirmed': False,
        'confirmed': False,
        'rule': 'CLOSED_1H_BREAK_BEYOND_STRUCTURE_PLUS_CURRENT_HOLD_ON_BREAKOUT_SIDE',
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'production_threshold_changed': False,
        'production_scoring_changed': False,
        'live_execution': False,
    }
    if not relevant or level is None:
        if relevant and level is None:
            result['state'] = 'UNKNOWN_NO_STRUCTURE_LEVEL'
        return result

    rows = list(klines or [])
    if len(rows) < 2:
        return result

    closed = _f(rows[-2].get('close'))
    current = _f(rows[-1].get('close'))
    if closed is None or current is None:
        return result

    atr = _atr_from_klines(rows, 14)
    buffer_abs = max(abs(level) * 0.0005, (atr or 0.0) * 0.10)
    if direction == 'LONG':
        break_ok = closed >= level + buffer_abs
        hold_ok = current >= level
    else:
        break_ok = closed <= level - buffer_abs
        hold_ok = current <= level

    confirmed = bool(break_ok and hold_ok)
    result.update({
        'state': 'CONFIRMED_CLOSE_HOLD' if confirmed else 'UNCONFIRMED_STRUCTURE_BREAK',
        'closed_candle_close': round(closed, 10),
        'current_price': round(current, 10),
        'confirmation_buffer': round(buffer_abs, 10),
        'closed_break_confirmed': bool(break_ok),
        'hold_confirmed': bool(hold_ok),
        'confirmed': confirmed,
    })
    return result


def combined_shadow_from_row(row, threshold=68.0, klines=None):
    base = fourth_vote_shadow_from_row(row, threshold)
    structure = structure_confirmation_from_row(row, klines)
    direction = str((row or {}).get('direction') or '')
    fourth_qualified = bool(base.get('shadow_qualified'))

    # Fail closed inside SHADOW only when close-prior-structure evidence is relevant.
    # UNKNOWN is deliberately treated as unconfirmed for research classification,
    # but this never mutates Production.
    structure_veto = bool(structure.get('relevant') and not structure.get('confirmed'))
    combined_qualified = bool(fourth_qualified and not structure_veto)
    return {
        **base,
        'source': VERSION,
        'fourth_vote_shadow_qualified': fourth_qualified,
        'structure_confirmation': structure,
        'structure_confirmation_veto': structure_veto,
        # Compatibility field retained for existing consumers.
        'long_close_structure_veto': bool(direction == 'LONG' and structure_veto),
        'combined_shadow_qualified': combined_qualified,
        'combined_shadow_decision': 'QUALIFIED' if combined_qualified else 'WAIT',
        'combined_qualification_changed_vs_production': bool(base.get('production_qualified') != combined_qualified),
        'methodology': 'FOURTH_VOTE_SHADOW_PLUS_SYMMETRIC_CLOSED_1H_STRUCTURE_BREAK_AND_HOLD',
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'production_scoring_changed': False,
        'production_threshold_changed': False,
        'live_execution': False,
    }


def install(atlas):
    original_get = atlas.Handler.do_GET

    def current_shadow(symbol):
        symbol = str(symbol or '').upper().replace('BINANCE:', '')
        if symbol not in atlas.ON_DEMAND_SYMBOLS:
            return {
                'ok': False, 'error': 'unsupported symbol', 'source': VERSION,
                'supported_symbols': list(atlas.ON_DEMAND_SYMBOLS),
                'research_only': True, 'can_override_production': False,
                'live_execution': False,
            }
        btc = atlas._spot_klines('BTCUSDT')
        row = atlas.cloud_score_symbol(symbol, btc)
        if not isinstance(row, dict):
            return {
                'ok': True, 'source': VERSION, 'symbol': symbol,
                'production_candidate_available': False,
                'research_only': True, 'shadow_only': True,
                'can_override_production': False, 'live_execution': False,
            }
        market_klines = atlas._spot_klines(symbol)
        payload = combined_shadow_from_row(row, float(atlas.CLOUD_FORWARD_MIN_SCORE), market_klines)
        payload['ok'] = True
        payload['symbol'] = symbol
        payload['scoring_version'] = row.get('scoring_version')
        payload['score_attribution'] = row.get('score_attribution')
        return payload

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/research/long-close-structure-shadow':
            q = urllib.parse.parse_qs(parsed.query)
            symbol = q.get('symbol', ['BTCUSDT'])[0]
            try:
                result = current_shadow(symbol)
                return self._json(result, 200 if result.get('ok') else 400)
            except Exception as exc:
                return self._json({
                    'ok': False, 'error': f'{type(exc).__name__}: {exc}',
                    'source': VERSION, 'research_only': True, 'shadow_only': True,
                    'can_override_production': False, 'live_execution': False,
                }, 500)
        return original_get(self)

    atlas.Handler.do_GET = do_GET
    atlas.long_close_structure_shadow = current_shadow
    atlas.LONG_CLOSE_STRUCTURE_SHADOW_VERSION = VERSION
    return {
        'version': VERSION,
        'endpoint': '/api/research/long-close-structure-shadow',
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'production_scoring_changed': False,
        'production_threshold_changed': False,
        'live_execution': False,
        'confirmation_rule': 'CLOSED_1H_BREAK_BEYOND_STRUCTURE_PLUS_CURRENT_HOLD_ON_BREAKOUT_SIDE',
    }
