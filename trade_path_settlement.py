"""Read-only TP/SL path settlement for frozen ATLAS forward observations.

This layer never changes ATLAS scoring, thresholds, signals, Pattern Memory or
execution. New observations may be enriched with an auditable frozen geometry
when the existing ATLAS row already contains enough information to derive it.
"""

import json
import threading
import time
import urllib.parse
import urllib.request

MAX_HORIZON_H = 24
CACHE_SECONDS = 300
_CACHE = {}
_CACHE_LOCK = threading.RLock()


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def freeze_geometry(row):
    x = dict(row or {})
    if x.get('frozen_trade_geometry'):
        return x

    entry = _fnum(x.get('entry'))
    rr2 = _fnum(x.get('rr_tp2'))
    direction = str(x.get('direction') or '').upper()
    sd = _fnum(x.get('support_distance_pct'))
    rd = _fnum(x.get('resistance_distance_pct'))
    if not entry or entry <= 0 or direction not in ('LONG', 'SHORT') or not rr2 or rr2 <= 0:
        x['trade_geometry_status'] = 'UNAVAILABLE'
        return x

    if direction == 'LONG':
        if rd is None or rd <= 0:
            x['trade_geometry_status'] = 'UNAVAILABLE'
            return x
        tp2 = entry * (1 + rd / 100.0)
        reward = tp2 - entry
        risk = reward / rr2
        sl = entry - risk
        tp1 = entry + risk
    else:
        if sd is None or sd <= 0:
            x['trade_geometry_status'] = 'UNAVAILABLE'
            return x
        tp2 = entry * (1 - sd / 100.0)
        reward = entry - tp2
        risk = reward / rr2
        sl = entry + risk
        tp1 = entry - risk

    if risk <= 0 or sl <= 0 or tp1 <= 0 or tp2 <= 0:
        x['trade_geometry_status'] = 'UNAVAILABLE'
        return x

    x['frozen_trade_geometry'] = {
        'entry': round(entry, 12),
        'stop_loss': round(sl, 12),
        'tp1': round(tp1, 12),
        'tp2': round(tp2, 12),
        'risk_abs': round(risk, 12),
        'rr_tp1': 1.0,
        'rr_tp2': round(rr2, 6),
        'direction': direction,
        'method': 'STRUCTURAL_TP2_PLUS_FROZEN_RR',
        'tp1_method': 'ONE_R_CHECKPOINT',
        'frozen_at_observation': True,
    }
    x['trade_geometry_status'] = 'FROZEN'
    return x


def _request_klines(symbol, interval, start_ms, end_ms, limit=1000):
    path = (
        '/api/v3/klines?symbol=' + urllib.parse.quote(symbol) +
        '&interval=' + urllib.parse.quote(interval) +
        '&startTime=' + str(int(start_ms)) +
        '&endTime=' + str(int(end_ms)) +
        '&limit=' + str(int(limit))
    )
    urls = [
        'https://data-api.binance.vision' + path,
        'https://api-gcp.binance.com' + path,
        'https://api1.binance.com' + path,
    ]
    errors = []
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ATLAS-Outcome/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode('utf-8'))
            if not isinstance(raw, list):
                raise RuntimeError('invalid kline response')
            return [{
                'open_time': int(k[0]),
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'close_time': int(k[6]),
            } for k in raw]
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError('all spot candle providers failed: ' + ' | '.join(errors))


def _cached_5m(symbol, start_ms, end_ms):
    key = (symbol, int(start_ms // 300000), int(end_ms // 300000))
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached['at'] < CACHE_SECONDS:
            return cached['rows']
    rows = _request_klines(symbol, '5m', start_ms, end_ms, 400)
    with _CACHE_LOCK:
        _CACHE[key] = {'at': now, 'rows': rows}
    return rows


def _touches(candle, price):
    return candle['low'] <= price <= candle['high']


def _first_event(candles, geometry, allow_ambiguous=True):
    sl = float(geometry['stop_loss'])
    tp1 = float(geometry['tp1'])
    tp2 = float(geometry['tp2'])
    tp1_seen = False
    for candle in candles:
        hit_sl = _touches(candle, sl)
        hit_tp1 = _touches(candle, tp1)
        hit_tp2 = _touches(candle, tp2)
        if hit_sl and (hit_tp1 or hit_tp2):
            return {'event': 'SAME_CANDLE_AMBIGUOUS' if allow_ambiguous else 'AMBIGUOUS', 'candle': candle, 'tp1_seen_before': tp1_seen}
        if hit_sl:
            return {'event': 'SL', 'candle': candle, 'tp1_seen_before': tp1_seen}
        if hit_tp2:
            return {'event': 'TP2', 'candle': candle, 'tp1_seen_before': True}
        if hit_tp1:
            tp1_seen = True
    return {'event': 'TP1_ONLY' if tp1_seen else 'NONE', 'candle': None, 'tp1_seen_before': tp1_seen}


def _resolve_same_candle(symbol, candle, geometry):
    rows = _request_klines(symbol, '1m', candle['open_time'], candle['close_time'], 10)
    return _first_event(rows, geometry, allow_ambiguous=False)


def settle_row(row, now_ms=None):
    x = freeze_geometry(row)
    geometry = x.get('frozen_trade_geometry')
    base = {
        'id': x.get('id'), 'symbol': x.get('symbol'), 'direction': x.get('direction'),
        'captured_at': x.get('captured_at'), 'captured_at_ms': x.get('captured_at_ms'),
        'signal_qualified': bool(x.get('champion_take')), 'geometry': geometry,
        'geometry_status': x.get('trade_geometry_status') or ('FROZEN' if geometry else 'UNAVAILABLE'),
        'research_only': True, 'live_execution': False,
    }
    if not geometry:
        return {**base, 'path_outcome': 'GEOMETRY_UNAVAILABLE', 'terminal': False, 'r_multiple': None}
    start_ms = int(x.get('captured_at_ms') or 0)
    if not start_ms:
        return {**base, 'path_outcome': 'TIMESTAMP_UNAVAILABLE', 'terminal': False, 'r_multiple': None}
    now_ms = int(now_ms or time.time() * 1000)
    end_ms = min(now_ms, start_ms + MAX_HORIZON_H * 3600000)
    if end_ms <= start_ms:
        return {**base, 'path_outcome': 'OPEN', 'terminal': False, 'r_multiple': None}
    try:
        candles = _cached_5m(str(x.get('symbol')), start_ms, end_ms)
        event = _first_event(candles, geometry)
        if event['event'] == 'SAME_CANDLE_AMBIGUOUS' and event.get('candle'):
            resolved = _resolve_same_candle(str(x.get('symbol')), event['candle'], geometry)
            if resolved['event'] in ('SL', 'TP2'):
                event = resolved
            else:
                event = {'event': 'AMBIGUOUS', 'candle': event['candle'], 'tp1_seen_before': event.get('tp1_seen_before', False)}
    except Exception as exc:
        return {**base, 'path_outcome': 'MARKET_DATA_ERROR', 'terminal': False, 'r_multiple': None, 'error': str(exc)}

    rr2 = float(geometry.get('rr_tp2') or 0)
    elapsed_h = max(0.0, (end_ms - start_ms) / 3600000.0)
    ev = event['event']
    if ev == 'SL':
        outcome, r, terminal = 'LOSS', -1.0, True
    elif ev == 'TP2':
        outcome, r, terminal = 'WIN_TP2', rr2, True
    elif ev == 'AMBIGUOUS':
        outcome, r, terminal = 'AMBIGUOUS', None, False
    elif ev == 'TP1_ONLY':
        if elapsed_h >= MAX_HORIZON_H:
            outcome, r, terminal = 'WIN_TP1_EXPIRED', 1.0, True
        else:
            outcome, r, terminal = 'OPEN_AFTER_TP1', None, False
    else:
        if elapsed_h >= MAX_HORIZON_H:
            outcome, r, terminal = 'EXPIRED', 0.0, True
        else:
            outcome, r, terminal = 'OPEN', None, False

    candle = event.get('candle') or {}
    return {
        **base, 'path_outcome': outcome, 'path_event': ev, 'terminal': terminal,
        'r_multiple': r, 'event_time_ms': candle.get('open_time'),
        'evaluated_through_ms': end_ms, 'elapsed_hours': round(elapsed_h, 3),
        'settlement_method': '5M_PATH_WITH_1M_SAME_CANDLE_RESOLUTION',
    }


def install_geometry_freezer(collector):
    if getattr(collector, '_TRADE_GEOMETRY_FREEZER_INSTALLED', False):
        return getattr(collector, 'TRADE_GEOMETRY_FREEZER_STATE', {})
    original = collector.forward_observe
    state = {'enabled': True, 'frozen': 0, 'unavailable': 0, 'errors': 0}
    def wrapped(payload):
        try:
            enriched = freeze_geometry(payload)
            if enriched.get('frozen_trade_geometry'):
                state['frozen'] += 1
            else:
                state['unavailable'] += 1
            return original(enriched)
        except Exception:
            state['errors'] += 1
            return original(payload)
    collector.forward_observe = wrapped
    collector.TRADE_GEOMETRY_FREEZER_STATE = state
    collector._TRADE_GEOMETRY_FREEZER_INSTALLED = True
    return state
