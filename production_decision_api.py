"""Single source of truth for the ATLAS browser decision card.

Exposes the same production cloud scorer used by the research runtime and
normalizes it into LONG / SHORT / WAIT with explicit WAIT diagnostics and
score attribution. V3 adds a short in-memory cache and a bulk endpoint so
monitoring does not hammer Render with seven independent market-data requests.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSION = "PRODUCTION_DECISION_API_V3"
CACHE_TTL_SECONDS = 75
_CACHE = {}
_CACHE_LOCK = threading.Lock()


def install(atlas):
    original_get = atlas.Handler.do_GET

    def _cached(symbol):
        now = time.time()
        with _CACHE_LOCK:
            item = _CACHE.get(symbol)
            if item and now - item['ts'] <= CACHE_TTL_SECONDS:
                out = dict(item['value'])
                out['cache_hit'] = True
                out['cache_age_seconds'] = round(now - item['ts'], 3)
                return out
        return None

    def _store(symbol, value):
        with _CACHE_LOCK:
            _CACHE[symbol] = {'ts': time.time(), 'value': dict(value)}

    def build_decision(symbol, use_cache=True):
        symbol = str(symbol or '').upper().replace('BINANCE:', '')
        if symbol not in atlas.ON_DEMAND_SYMBOLS:
            return {
                'ok': False,
                'error': 'unsupported symbol',
                'supported_symbols': list(atlas.ON_DEMAND_SYMBOLS),
                'source': VERSION,
            }

        if use_cache:
            hit = _cached(symbol)
            if hit is not None:
                return hit

        started = time.time()
        btc = atlas._spot_klines('BTCUSDT')
        ks = btc if symbol == 'BTCUSDT' else atlas._spot_klines(symbol)
        if len(ks) < 100:
            return {'ok': False, 'error': 'insufficient candles', 'source': VERSION}

        closes = [x['close'] for x in ks]
        vols = [x['volume'] for x in ks]
        px = closes[-1]
        ema20 = atlas._ema(closes[-80:], 20)
        ema50 = atlas._ema(closes[-120:], 50)
        rsi = atlas._rsi(closes, 14)
        atr = atlas._atr(ks, 14)
        mom24 = ((px / closes[-25]) - 1) * 100 if len(closes) >= 25 and closes[-25] else 0.0
        long_votes = sum((px >= ema20, ema20 >= ema50, rsi >= 50, mom24 >= 0))
        short_votes = sum((px <= ema20, ema20 <= ema50, rsi <= 50, mom24 <= 0))
        vol_base = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else vols[-1]
        rv = vols[-1] / vol_base if vol_base else 1.0
        sup, res, sd, rd = atlas._cloud_sr(ks)

        row = atlas.cloud_score_symbol(symbol, btc)
        threshold = float(atlas.CLOUD_FORWARD_MIN_SCORE)

        candidate_direction = row.get('direction') if isinstance(row, dict) else None
        score = atlas.fnum(row.get('final_score')) if isinstance(row, dict) else None
        qualified = bool(candidate_direction in ('LONG', 'SHORT') and score is not None and score >= threshold)
        decision = candidate_direction if qualified else 'WAIT'

        if row is None:
            if max(long_votes, short_votes) < 3 or long_votes == short_votes:
                reason = 'NO_DIRECTIONAL_CONSENSUS'
            else:
                reason = 'SCORER_RETURNED_NO_CANDIDATE'
        elif not qualified:
            reason = 'SCORE_BELOW_SIGNAL_THRESHOLD'
        else:
            reason = 'SIGNAL_QUALIFIED'

        stop = target = None
        rr = None
        if isinstance(row, dict):
            rr = atlas.fnum(row.get('rr_tp2'))
            if candidate_direction == 'LONG' and atr:
                stop = px - atr * 1.2
                target = res
            elif candidate_direction == 'SHORT' and atr:
                stop = px + atr * 1.2
                target = sup

        result = {
            'ok': True,
            'source': VERSION,
            'scoring_version': (row or {}).get('scoring_version') if isinstance(row, dict) else None,
            'symbol': symbol,
            'decision': decision,
            'candidate_direction': candidate_direction,
            'signal_qualified': qualified,
            'wait_reason': None if qualified else reason,
            'score': score,
            'signal_threshold': threshold,
            'score_gap_to_signal': round(threshold - score, 3) if score is not None and score < threshold else 0,
            'score_attribution': (row or {}).get('score_attribution') if isinstance(row, dict) else None,
            'entry': px,
            'stop_loss': stop,
            'take_profit': target,
            'risk_reward': rr,
            'direction_votes': (row or {}).get('direction_votes') if isinstance(row, dict) else max(long_votes, short_votes),
            'direction_votes_long': (row or {}).get('direction_votes_long') if isinstance(row, dict) else long_votes,
            'direction_votes_short': (row or {}).get('direction_votes_short') if isinstance(row, dict) else short_votes,
            'execution_decision': (row or {}).get('execution_decision') if isinstance(row, dict) else None,
            'trade_plan_status': (row or {}).get('trade_plan_status') if isinstance(row, dict) else None,
            'playbook': (row or {}).get('playbook_primary') if isinstance(row, dict) else None,
            'futures_available': (row or {}).get('futures_available') if isinstance(row, dict) else None,
            'futures_provider': (row or {}).get('futures_provider') if isinstance(row, dict) else None,
            'futures_score': (row or {}).get('futures_score') if isinstance(row, dict) else None,
            'relative_strength_score': (row or {}).get('relative_strength_score') if isinstance(row, dict) else None,
            'volume_quality': (row or {}).get('volume_quality') if isinstance(row, dict) else None,
            'relative_volume': (row or {}).get('relative_volume') if isinstance(row, dict) else round(rv, 3),
            'regime': (row or {}).get('regime') if isinstance(row, dict) else None,
            'indicators': {
                'ema20': ema20,
                'ema50': ema50,
                'rsi14': rsi,
                'atr14': atr,
                'volume_ratio': rv,
                'momentum_24h_pct': mom24,
            },
            'generated_at': atlas.now_iso(),
            'generation_ms': round((time.time() - started) * 1000, 1),
            'cache_hit': False,
            'cache_age_seconds': 0,
            'research_only': True,
            'live_execution': False,
        }
        _store(symbol, result)
        return result

    def build_all_decisions():
        symbols = list(atlas.ON_DEMAND_SYMBOLS)
        decisions = {}
        errors = {}
        # A small worker pool reduces wall-clock time without creating a burst
        # large enough to overload upstream market-data providers.
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix='atlas-decision') as pool:
            futures = {pool.submit(build_decision, s, True): s for s in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    decisions[symbol] = future.result()
                except Exception as exc:
                    errors[symbol] = f'{type(exc).__name__}: {exc}'
                    stale = _cached(symbol)
                    if stale is not None:
                        stale['stale_fallback'] = True
                        stale['stale_reason'] = errors[symbol]
                        decisions[symbol] = stale
                    else:
                        decisions[symbol] = {
                            'ok': False,
                            'symbol': symbol,
                            'error': errors[symbol],
                            'source': VERSION,
                            'research_only': True,
                            'live_execution': False,
                        }
        return {
            'ok': True,
            'source': VERSION,
            'generated_at': atlas.now_iso(),
            'symbols': symbols,
            'decisions': decisions,
            'error_count': len(errors),
            'errors': errors,
            'cache_ttl_seconds': CACHE_TTL_SECONDS,
            'research_only': True,
            'live_execution': False,
        }

    atlas.production_decision = build_decision
    atlas.production_decisions_snapshot = build_all_decisions

    def do_GET(self):
        import urllib.parse
        u = urllib.parse.urlparse(self.path)
        if u.path == '/api/decision/current':
            q = urllib.parse.parse_qs(u.query)
            symbol = q.get('symbol', ['BTCUSDT'])[0]
            try:
                result = build_decision(symbol)
                return self._json(result, 200 if result.get('ok') else 400)
            except Exception as exc:
                stale = _cached(str(symbol).upper().replace('BINANCE:', ''))
                if stale is not None:
                    stale['stale_fallback'] = True
                    stale['stale_reason'] = f'{type(exc).__name__}: {exc}'
                    return self._json(stale, 200)
                return self._json({
                    'ok': False,
                    'error': f'{type(exc).__name__}: {exc}',
                    'source': VERSION,
                    'research_only': True,
                    'live_execution': False,
                }, 500)
        if u.path == '/api/decision/all':
            try:
                return self._json(build_all_decisions())
            except Exception as exc:
                return self._json({
                    'ok': False,
                    'error': f'{type(exc).__name__}: {exc}',
                    'source': VERSION,
                    'research_only': True,
                    'live_execution': False,
                }, 500)
        return original_get(self)

    atlas.Handler.do_GET = do_GET
    return {
        'enabled': True,
        'version': VERSION,
        'endpoint': '/api/decision/current',
        'bulk_endpoint': '/api/decision/all',
        'cache_ttl_seconds': CACHE_TTL_SECONDS,
    }
