"""Prospective research-only LONG+CLOSE structure veto shadow.

Builds on the frozen fourth-vote shadow logic but does not mutate Production.
It exposes what the combined research candidate would decide while preserving
and reporting the real Production score/qualification separately.
"""
from __future__ import annotations

import urllib.parse

from prospective_fourth_vote_shadow import shadow_from_row as fourth_vote_shadow_from_row

VERSION = 'ATLAS_PROSPECTIVE_LONG_CLOSE_STRUCTURE_SHADOW_V1'


def combined_shadow_from_row(row, threshold=68.0):
    base = fourth_vote_shadow_from_row(row, threshold)
    obstacle = str((row or {}).get('score_attribution', {}).get('obstacle_reason') or '')
    direction = str((row or {}).get('direction') or '')
    long_close_veto = bool(direction == 'LONG' and obstacle == 'CLOSE_PRIOR_STRUCTURE')
    fourth_qualified = bool(base.get('shadow_qualified'))
    combined_qualified = bool(fourth_qualified and not long_close_veto)
    return {
        **base,
        'source': VERSION,
        'fourth_vote_shadow_qualified': fourth_qualified,
        'obstacle_reason': obstacle,
        'long_close_structure_veto': long_close_veto,
        'combined_shadow_qualified': combined_qualified,
        'combined_shadow_decision': 'QUALIFIED' if combined_qualified else 'WAIT',
        'combined_qualification_changed_vs_production': bool(base.get('production_qualified') != combined_qualified),
        'methodology': 'FOURTH_VOTE_PREMIUM_DEMOTION_THEN_VETO_LONG_WITH_CLOSE_PRIOR_STRUCTURE',
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
        payload = combined_shadow_from_row(row, float(atlas.CLOUD_FORWARD_MIN_SCORE))
        payload['ok'] = True
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
        'can_override_production': False,
        'production_threshold_changed': False,
        'live_execution': False,
    }
