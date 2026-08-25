"""Frozen trade geometry + read-only TP/SL path settlement for ATLAS.

This module is intentionally isolated from the decision engine. It never changes
scores, thresholds, LONG/SHORT decisions, Pattern Memory, alerts, or execution.
It only freezes geometry for newly stored observations when the existing ATLAS
row contains enough information, then evaluates that frozen geometry later.

Signal scope follows the canonical Production-qualified semantics from
trade_outcome_ledger. Legacy research champion_take is never used as a synonym
for a Production signal.
"""

import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import trade_outcome_ledger

MAX_HORIZON_H = 24
CACHE_SECONDS = 300
PROVIDER_TIMEOUT_SECONDS = 6
MARKET_DATA_CIRCUIT_SECONDS = 60
GEOMETRY_VERSION = 'ATLAS_GEOMETRY_V3_STRUCTURAL_TP2_FROZEN_RR'
_CACHE = {}
_CACHE_LOCK = threading.RLock()
_MARKET_DATA_CIRCUIT = {'open_until': 0.0, 'last_error': None, 'failures': 0, 'opened_at': None}
_MARKET_DATA_CIRCUIT_LOCK = threading.RLock()


def _fnum(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_production_signal(row):
    return trade_outcome_ledger.is_production_signal(row or {})


def _is_research_champion(row):
    return trade_outcome_ledger.is_research_champion(row or {})


def derive_geometry(payload):
    """Derive immutable SL/TP geometry only from already-existing ATLAS fields."""
    x = dict(payload or {})
    entry = _fnum(x.get('entry'))
    rr2 = _fnum(x.get('rr_tp2'))
    direction = str(x.get('direction') or '').upper()
    sd = _fnum(x.get('support_distance_pct'))
    rd = _fnum(x.get('resistance_distance_pct'))
    if not entry or entry <= 0 or direction not in ('LONG', 'SHORT') or not rr2 or rr2 <= 0:
        return None

    if direction == 'LONG':
        if rd is None or rd <= 0:
            return None
        tp2 = entry * (1 + rd / 100.0)
        reward = tp2 - entry
        risk = reward / rr2
        sl = entry - risk
        tp1 = entry + risk
    else:
        if sd is None or sd <= 0:
            return None
        tp2 = entry * (1 - sd / 100.0)
        reward = entry - tp2
        risk = reward / rr2
        sl = entry + risk
        tp1 = entry - risk

    if risk <= 0 or min(sl, tp1, tp2) <= 0:
        return None
    return {
        'entry': round(entry, 12),
        'stop_loss': round(sl, 12),
        'tp1': round(tp1, 12),
        'tp2': round(tp2, 12),
        'risk_abs': round(risk, 12),
        'rr_tp1': 1.0,
        'rr_tp2': round(rr2, 6),
        'direction': direction,
        'geometry_version': GEOMETRY_VERSION,
        'method': 'STRUCTURAL_TP2_PLUS_FROZEN_RR',
        'tp1_method': 'ONE_R_CHECKPOINT',
        'tp1_is_terminal_exit': False,
        'frozen_at_observation': True,
    }


def geometry_archive_path(collector):
    return Path(collector.DATA) / 'trade_geometry.jsonl'


def read_geometry_archive(collector):
    path = geometry_archive_path(collector)
    out = []
    if path.exists():
        with path.open() as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def geometry_by_forward_id(collector):
    return {str(x.get('forward_observation_id')): x for x in read_geometry_archive(collector) if x.get('forward_observation_id')}


def _persist_geometry(collector, forward_row, geometry):
    forward_id = str((forward_row or {}).get('id') or '')
    if not forward_id or not geometry:
        return {'stored': False, 'reason': 'MISSING_ID_OR_GEOMETRY'}
    path = geometry_archive_path(collector)
    lock = getattr(collector, 'ARCHIVE_LOCK', None) or threading.RLock()
    with lock:
        existing = read_geometry_archive(collector)
        if any(str(x.get('forward_observation_id') or '') == forward_id for x in existing):
            return {'stored': False, 'reason': 'DEDUP_FORWARD_ID'}
        rec = {
            'schema': 'ATLAS_FROZEN_TRADE_GEOMETRY_V3_VERSIONED_COHORT',
            'geometry_generation': geometry.get('geometry_version'),
            'forward_observation_id': forward_id,
            'captured_at': forward_row.get('captured_at'),
            'captured_at_ms': forward_row.get('captured_at_ms'),
            'symbol': forward_row.get('symbol'),
            'direction': forward_row.get('direction'),
            'signal_qualified': _is_production_signal(forward_row),
            'production_signal_qualified': _is_production_signal(forward_row),
            'research_champion': _is_research_champion(forward_row),
            'geometry': geometry,
            'research_only': True,
            'live_execution': False,
        }
        with path.open('a') as f:
            f.write(json.dumps(rec, separators=(',', ':')) + '\n')
        return {'stored': True, 'record': rec}


def market_data_circuit_state():
    with _MARKET_DATA_CIRCUIT_LOCK:
        now = time.time()
        return {
            'open': bool(_MARKET_DATA_CIRCUIT['open_until'] > now),
            'open_until': _MARKET_DATA_CIRCUIT['open_until'],
            'last_error': _MARKET_DATA_CIRCUIT['last_error'],
            'failures': _MARKET_DATA_CIRCUIT['failures'],
            'opened_at': _MARKET_DATA_CIRCUIT['opened_at'],
        }


def _circuit_check():
    with _MARKET_DATA_CIRCUIT_LOCK:
        now = time.time()
        if _MARKET_DATA_CIRCUIT['open_until'] > now:
            remaining = max(0.0, _MARKET_DATA_CIRCUIT['open_until'] - now)
            raise RuntimeError(f'market data circuit open; retry after {remaining:.1f}s; last_error={_MARKET_DATA_CIRCUIT["last_error"]}')
        if _MARKET_DATA_CIRCUIT['open_until']:
            _MARKET_DATA_CIRCUIT['open_until'] = 0.0


def _circuit_success():
    with _MARKET_DATA_CIRCUIT_LOCK:
        _MARKET_DATA_CIRCUIT['open_until'] = 0.0
        _MARKET_DATA_CIRCUIT['last_error'] = None
        _MARKET_DATA_CIRCUIT['failures'] = 0
        _MARKET_DATA_CIRCUIT['opened_at'] = None


def _circuit_fail(error):
    with _MARKET_DATA_CIRCUIT_LOCK:
        now = time.time()
        _MARKET_DATA_CIRCUIT['failures'] += 1
        _MARKET_DATA_CIRCUIT['last_error'] = str(error)
        _MARKET_DATA_CIRCUIT['opened_at'] = now
        _MARKET_DATA_CIRCUIT['open_until'] = now + MARKET_DATA_CIRCUIT_SECONDS


def _request_klines(symbol, interval, start_ms, end_ms, limit=1000):
    _circuit_check()
    path = '/api/v3/klines?symbol=' + urllib.parse.quote(symbol) + '&interval=' + urllib.parse.quote(interval) + '&startTime=' + str(int(start_ms)) + '&endTime=' + str(int(end_ms)) + '&limit=' + str(int(limit))
    errors = []
    for base in ('https://data-api.binance.vision', 'https://api-gcp.binance.com', 'https://api1.binance.com'):
        try:
            req = urllib.request.Request(base + path, headers={'User-Agent': 'ATLAS-Outcome/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=PROVIDER_TIMEOUT_SECONDS) as response:
                raw = json.loads(response.read().decode('utf-8'))
            if not isinstance(raw, list):
                raise RuntimeError('invalid kline response')
            rows = [{'open_time': int(k[0]), 'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4]), 'close_time': int(k[6])} for k in raw]
            _circuit_success()
            return rows
        except Exception as exc:
            errors.append(f'{base}: {exc}')
    error = 'all spot candle providers failed: ' + ' | '.join(errors)
    _circuit_fail(error)
    raise RuntimeError(error)


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
    sl, tp1, tp2 = float(geometry['stop_loss']), float(geometry['tp1']), float(geometry['tp2'])
    tp1_seen = False
    for candle in candles:
        hit_sl, hit_tp1, hit_tp2 = _touches(candle, sl), _touches(candle, tp1), _touches(candle, tp2)
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
    return _first_event(_request_klines(symbol, '1m', candle['open_time'], candle['close_time'], 10), geometry, allow_ambiguous=False)


def settle_row(row, geometry_record=None, now_ms=None, candle_loader=None):
    geometry = (geometry_record or {}).get('geometry') if geometry_record else None
    base = {
        'id': row.get('id'), 'symbol': row.get('symbol'), 'direction': row.get('direction'),
        'captured_at': row.get('captured_at'), 'captured_at_ms': row.get('captured_at_ms'),
        'score': _fnum(row.get('final_score')) if row.get('final_score') is not None else _fnum(row.get('champion_score')),
        'entry': _fnum(row.get('entry')), 'source': row.get('auto_source'),
        'signal_qualified': _is_production_signal(row),
        'production_signal_qualified': _is_production_signal(row),
        'research_champion': _is_research_champion(row),
        'geometry_generation': (geometry or {}).get('geometry_version') or (geometry_record or {}).get('geometry_generation'),
        'geometry': geometry, 'geometry_status': 'FROZEN' if geometry else 'UNAVAILABLE',
        'research_only': True, 'live_execution': False,
    }
    if not geometry:
        return {**base, 'path_outcome': 'GEOMETRY_UNAVAILABLE', 'terminal': False, 'r_multiple': None}
    start_ms = int(row.get('captured_at_ms') or 0)
    if not start_ms:
        return {**base, 'path_outcome': 'TIMESTAMP_UNAVAILABLE', 'terminal': False, 'r_multiple': None}
    now_ms = int(now_ms or time.time() * 1000)
    end_ms = min(now_ms, start_ms + MAX_HORIZON_H * 3600000)
    if end_ms <= start_ms:
        return {**base, 'path_outcome': 'OPEN', 'terminal': False, 'r_multiple': None}
    try:
        loader = candle_loader or _cached_5m
        candles = loader(str(row.get('symbol')), start_ms, end_ms)
        event = _first_event(candles, geometry)
        if candle_loader is None and event['event'] == 'SAME_CANDLE_AMBIGUOUS' and event.get('candle'):
            resolved = _resolve_same_candle(str(row.get('symbol')), event['candle'], geometry)
            event = resolved if resolved['event'] in ('SL', 'TP2') else {'event': 'AMBIGUOUS', 'candle': event['candle']}
    except Exception as exc:
        return {**base, 'path_outcome': 'MARKET_DATA_ERROR', 'terminal': False, 'r_multiple': None, 'error': str(exc)}

    elapsed_h = max(0.0, (end_ms - start_ms) / 3600000.0)
    ev, rr2 = event['event'], float(geometry.get('rr_tp2') or 0)
    if ev == 'SL':
        outcome, r, terminal = 'LOSS', -1.0, True
    elif ev == 'TP2':
        outcome, r, terminal = 'WIN_TP2', rr2, True
    elif ev in ('AMBIGUOUS', 'SAME_CANDLE_AMBIGUOUS'):
        outcome, r, terminal = 'AMBIGUOUS', None, False
    elif ev == 'TP1_ONLY':
        outcome, r, terminal = ('EXPIRED_AFTER_TP1', 0.0, True) if elapsed_h >= MAX_HORIZON_H else ('OPEN_AFTER_TP1', None, False)
    else:
        outcome, r, terminal = ('EXPIRED', 0.0, True) if elapsed_h >= MAX_HORIZON_H else ('OPEN', None, False)
    candle = event.get('candle') or {}
    return {
        **base, 'path_outcome': outcome, 'path_event': ev, 'terminal': terminal,
        'r_multiple': r,
        'tp1_reached': bool(ev in ('TP1_ONLY', 'TP2') or event.get('tp1_seen_before')),
        'event_time_ms': candle.get('open_time'), 'evaluated_through_ms': end_ms,
        'elapsed_hours': round(elapsed_h, 3),
        'settlement_method': '5M_PATH_WITH_1M_SAME_CANDLE_RESOLUTION',
    }


def build_path_ledger(rows, geometry_map, scope='signals', symbol=None, limit=100, now_ms=None):
    scope = str(scope or 'signals').lower()
    if scope not in ('signals', 'champions', 'all'):
        raise ValueError('scope must be signals, champions or all')
    symbol = str(symbol or '').upper() or None
    selected = []
    for row in rows or []:
        if str(row.get('direction') or '').upper() not in ('LONG', 'SHORT'):
            continue
        if scope == 'signals' and not _is_production_signal(row):
            continue
        if scope == 'champions' and not _is_research_champion(row):
            continue
        if symbol and str(row.get('symbol') or '').upper() != symbol:
            continue
        selected.append(row)
    selected.sort(key=lambda x: int(x.get('captured_at_ms') or 0), reverse=True)
    selected = selected[:max(1, min(500, int(limit or 100)))]
    return [settle_row(row, geometry_map.get(str(row.get('id') or '')), now_ms=now_ms) for row in selected]


def summarize_path(items):
    terminal = [x for x in items if x.get('terminal')]
    wins = [x for x in terminal if x.get('path_outcome') == 'WIN_TP2']
    losses = [x for x in terminal if x.get('path_outcome') == 'LOSS']
    expired = [x for x in terminal if str(x.get('path_outcome') or '').startswith('EXPIRED')]
    rs = [float(x['r_multiple']) for x in terminal if x.get('r_multiple') is not None]
    positive_r = sum(x for x in rs if x > 0)
    negative_r = abs(sum(x for x in rs if x < 0))
    market_data_errors = [x for x in items if x.get('path_outcome') == 'MARKET_DATA_ERROR']
    return {
        'total': len(items), 'terminal': len(terminal), 'open': len(items) - len(terminal),
        'wins': len(wins), 'losses': len(losses), 'expired': len(expired),
        'win_rate_pct': round(100 * len(wins) / (len(wins) + len(losses)), 2) if wins or losses else None,
        'net_r': round(sum(rs), 4) if rs else None,
        'average_r': round(sum(rs) / len(rs), 4) if rs else None,
        'profit_factor_r': round(positive_r / negative_r, 4) if negative_r > 0 else (None if positive_r == 0 else 'INF'),
        'geometry_available': sum(1 for x in items if x.get('geometry_status') == 'FROZEN'),
        'geometry_unavailable': sum(1 for x in items if x.get('geometry_status') != 'FROZEN'),
        'tp1_reached': sum(1 for x in items if x.get('tp1_reached')),
        'ambiguous': sum(1 for x in items if x.get('path_outcome') == 'AMBIGUOUS'),
        'market_data_errors': len(market_data_errors),
        'market_data_circuit': market_data_circuit_state(),
        'scope_semantics': 'PRODUCTION_QUALIFIED_ONLY' if all(x.get('production_signal_qualified') for x in items) and items else None,
    }


def install_geometry_freezer(collector):
    if getattr(collector, '_TRADE_GEOMETRY_FREEZER_INSTALLED', False):
        return getattr(collector, 'TRADE_GEOMETRY_FREEZER_STATE', {})
    original = collector.forward_observe
    state = {'enabled': True, 'archive': str(geometry_archive_path(collector)), 'frozen': 0, 'unavailable': 0, 'deduped': 0, 'errors': 0, 'last_error': None}

    def wrapped(payload):
        try:
            geometry = derive_geometry(payload)
        except Exception as exc:
            geometry = None
            state['errors'] += 1
            state['last_error'] = f'derive: {exc}'
        result = original(payload)
        canonical = result.get('record') if isinstance(result, dict) and isinstance(result.get('record'), dict) else result if isinstance(result, dict) and result.get('id') else None
        if canonical is None:
            return result
        if geometry is None:
            state['unavailable'] += 1
            return result
        try:
            stored = _persist_geometry(collector, canonical, geometry)
            state['frozen' if stored.get('stored') else 'deduped'] += 1
            state['last_error'] = None
        except Exception as exc:
            state['errors'] += 1
            state['last_error'] = f'persist: {exc}'
        return result

    collector.forward_observe = wrapped
    collector.TRADE_GEOMETRY_FREEZER_STATE = state
    collector._TRADE_GEOMETRY_FREEZER_INSTALLED = True
    return state