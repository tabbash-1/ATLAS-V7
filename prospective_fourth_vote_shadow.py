"""Prospective research-only fourth-vote qualification shadow.

This module never mutates Production scoring, threshold, qualification, geometry,
or execution. It reuses the current Production scorer and exposes a separate
comparison endpoint so future observations can be evaluated prospectively.
"""
from __future__ import annotations

import urllib.parse

VERSION = 'ATLAS_PROSPECTIVE_FOURTH_VOTE_SHADOW_V1'


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def shadow_from_row(row, threshold=68.0):
    row = row or {}
    score = _f(row.get('final_score'))
    votes = int(_f(row.get('direction_votes'), 0) or 0)
    attr = row.get('score_attribution') or {}
    trend_base = _f(attr.get('trend_base'), 0.0) or 0.0
    premium = 4.0 if votes >= 4 and trend_base >= 68.0 else 0.0
    shadow_score = None if score is None else round(max(0.0, min(100.0, score - premium)))
    prod_qualified = bool(row.get('production_signal_qualified', score is not None and score >= threshold))
    shadow_qualified = bool(shadow_score is not None and shadow_score >= threshold)
    return {
        'source': VERSION,
        'symbol': row.get('symbol'),
        'direction': row.get('direction'),
        'production_score': score,
        'production_qualified': prod_qualified,
        'production_threshold': float(threshold),
        'direction_votes': votes,
        'trend_base': trend_base,
        'fourth_vote_premium_removed': premium,
        'shadow_score': shadow_score,
        'shadow_qualified': shadow_qualified,
        'qualification_changed': bool(prod_qualified != shadow_qualified),
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'production_scoring_changed': False,
        'production_threshold_changed': False,
        'live_execution': False,
        'methodology': 'REMOVE_ONLY_THE_INCREMENTAL_4_POINT_PREMIUM_FOR_A_FOURTH_ALIGNED_VOTE',
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
        payload = shadow_from_row(row, float(atlas.CLOUD_FORWARD_MIN_SCORE))
        payload['ok'] = True
        payload['scoring_version'] = row.get('scoring_version')
        payload['score_attribution'] = row.get('score_attribution')
        return payload

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/research/fourth-vote-shadow':
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
    atlas.fourth_vote_shadow = current_shadow
    atlas.FOURTH_VOTE_SHADOW_VERSION = VERSION
    return {
        'version': VERSION,
        'endpoint': '/api/research/fourth-vote-shadow',
        'research_only': True,
        'can_override_production': False,
        'production_threshold_changed': False,
        'live_execution': False,
    }
