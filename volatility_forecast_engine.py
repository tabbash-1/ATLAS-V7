"""ATLAS empirical volatility forecast engine (shadow research only).

The engine estimates plausible absolute price movement over 1h/4h/12h from the
actual kline sampling interval. It combines direct historical horizon returns
with recent/long realized volatility and an EWMA volatility estimate. It does not
claim calibrated probabilities and cannot approve/reject a Production trade.

No fake intrabar resolution is manufactured: if the supplied bars are coarser
than a requested horizon, that horizon is marked insufficient.
"""

from __future__ import annotations

import math
import statistics

VERSION = 'VOLATILITY_FORECAST_V1_EMPIRICAL_SHADOW'
DEFAULT_HORIZONS_H = (1, 4, 12)
MIN_BARS = 80
MIN_DIRECT_SAMPLES = 24


def _f(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _bar(row):
    """Normalize Binance-like arrays or dict klines to timestamp/high/low/close."""
    if isinstance(row, dict):
        ts = row.get('open_time', row.get('timestamp', row.get('time', row.get('t'))))
        high = row.get('high', row.get('h'))
        low = row.get('low', row.get('l'))
        close = row.get('close', row.get('c'))
    elif isinstance(row, (list, tuple)) and len(row) >= 5:
        ts, high, low, close = row[0], row[2], row[3], row[4]
    else:
        return None
    ts = _f(ts); high = _f(high); low = _f(low); close = _f(close)
    if None in (ts, high, low, close) or close <= 0 or high <= 0 or low <= 0:
        return None
    # Convert seconds to ms when needed.
    if ts < 10_000_000_000:
        ts *= 1000.0
    return {'ts': int(ts), 'high': high, 'low': low, 'close': close}


def _normalize(klines):
    rows = [_bar(x) for x in (klines or [])]
    rows = [x for x in rows if x is not None]
    rows.sort(key=lambda x: x['ts'])
    # Timestamp dedup, keeping the latest representation.
    by_ts = {x['ts']: x for x in rows}
    return [by_ts[k] for k in sorted(by_ts)]


def _quantile(values, q):
    xs = sorted(_f(x) for x in values if _f(x) is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def _std(values):
    xs = [_f(x) for x in values]
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    return statistics.stdev(xs)


def _ewma_sigma(returns, lam=0.94):
    xs = [_f(x) for x in returns]
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    var = xs[0] * xs[0]
    for r in xs[1:]:
        var = lam * var + (1.0 - lam) * r * r
    return math.sqrt(max(0.0, var))


def _pct_move_from_log_sigma(sigma):
    if sigma is None:
        return None
    # Symmetric small-return approximation expressed as percent.
    return sigma * 100.0


def _direct_abs_moves(closes, steps):
    if steps <= 0 or len(closes) <= steps:
        return []
    out = []
    for i in range(steps, len(closes)):
        a = closes[i - steps]; b = closes[i]
        if a > 0 and b > 0:
            out.append(abs(math.log(b / a)) * 100.0)
    return out


def analyze(symbol, klines, horizons_h=DEFAULT_HORIZONS_H):
    rows = _normalize(klines)
    normalized = str(symbol or '').upper().replace('BINANCE:', '')
    base = {
        'version': VERSION,
        'symbol': normalized,
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
        'probability_calibrated': False,
        'live_execution': False,
    }
    if len(rows) < MIN_BARS:
        return {
            **base,
            'status': 'INSUFFICIENT',
            'bars': len(rows),
            'minimum_bars': MIN_BARS,
            'reason': 'INSUFFICIENT_KLINE_HISTORY',
            'horizons': {},
        }

    gaps = [rows[i]['ts'] - rows[i - 1]['ts'] for i in range(1, len(rows)) if rows[i]['ts'] > rows[i - 1]['ts']]
    if not gaps:
        return {**base, 'status': 'INSUFFICIENT', 'bars': len(rows), 'reason': 'NO_TIME_INTERVAL', 'horizons': {}}
    interval_ms = int(statistics.median(gaps))
    bar_minutes = interval_ms / 60000.0
    closes = [x['close'] for x in rows]
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0 and closes[i] > 0]

    recent_n = min(len(log_returns), max(24, int(round(48 * 60 / bar_minutes))))
    long_n = min(len(log_returns), max(recent_n, int(round(168 * 60 / bar_minutes))))
    recent = log_returns[-recent_n:]
    long = log_returns[-long_n:]
    recent_sigma = _std(recent)
    long_sigma = _std(long)
    ewma_sigma = _ewma_sigma(long)
    vol_ratio = (recent_sigma / long_sigma) if recent_sigma is not None and long_sigma not in (None, 0) else None
    if vol_ratio is None:
        regime = 'UNKNOWN'
    elif vol_ratio >= 1.45:
        regime = 'VOL_EXPANSION'
    elif vol_ratio <= 0.72:
        regime = 'VOL_COMPRESSION'
    else:
        regime = 'VOL_NORMAL'

    horizons = {}
    for horizon in horizons_h:
        h = float(horizon)
        requested_minutes = h * 60.0
        if bar_minutes > requested_minutes * 1.05:
            horizons[str(int(h) if h.is_integer() else h)] = {
                'status': 'INSUFFICIENT',
                'horizon_h': h,
                'reason': 'BAR_INTERVAL_COARSER_THAN_HORIZON',
                'bar_minutes': round(bar_minutes, 4),
            }
            continue
        steps = max(1, int(round(requested_minutes / bar_minutes)))
        direct = _direct_abs_moves(closes, steps)
        direct_recent = direct[-min(len(direct), 240):]
        empirical_ready = len(direct_recent) >= MIN_DIRECT_SAMPLES

        p50 = _quantile(direct_recent, 0.50) if empirical_ready else None
        p80 = _quantile(direct_recent, 0.80) if empirical_ready else None
        p95 = _quantile(direct_recent, 0.95) if empirical_ready else None

        # Independent volatility-scaled references. They are diagnostics, not
        # calibrated confidence intervals.
        scale = math.sqrt(max(1.0, requested_minutes / bar_minutes))
        recent_scaled = _pct_move_from_log_sigma(recent_sigma * scale) if recent_sigma is not None else None
        ewma_scaled = _pct_move_from_log_sigma(ewma_sigma * scale) if ewma_sigma is not None else None
        long_scaled = _pct_move_from_log_sigma(long_sigma * scale) if long_sigma is not None else None

        horizons[str(int(h) if h.is_integer() else h)] = {
            'status': 'READY' if empirical_ready else 'INSUFFICIENT',
            'horizon_h': h,
            'steps': steps,
            'direct_samples': len(direct_recent),
            'minimum_direct_samples': MIN_DIRECT_SAMPLES,
            'empirical_abs_move_pct': {
                'p50': round(p50, 6) if p50 is not None else None,
                'p80': round(p80, 6) if p80 is not None else None,
                'p95': round(p95, 6) if p95 is not None else None,
            },
            'volatility_scaled_move_pct': {
                'recent_sigma_1x': round(recent_scaled, 6) if recent_scaled is not None else None,
                'ewma_sigma_1x': round(ewma_scaled, 6) if ewma_scaled is not None else None,
                'long_sigma_1x': round(long_scaled, 6) if long_scaled is not None else None,
            },
        }

    ready_count = sum(1 for x in horizons.values() if x.get('status') == 'READY')
    return {
        **base,
        'status': 'READY' if ready_count else 'INSUFFICIENT',
        'bars': len(rows),
        'bar_minutes': round(bar_minutes, 4),
        'latest_close': closes[-1],
        'recent_return_samples': len(recent),
        'long_return_samples': len(long),
        'recent_sigma_pct_per_bar': round(recent_sigma * 100, 8) if recent_sigma is not None else None,
        'long_sigma_pct_per_bar': round(long_sigma * 100, 8) if long_sigma is not None else None,
        'ewma_sigma_pct_per_bar': round(ewma_sigma * 100, 8) if ewma_sigma is not None else None,
        'recent_to_long_vol_ratio': round(vol_ratio, 6) if vol_ratio is not None else None,
        'volatility_regime': regime,
        'ready_horizons': ready_count,
        'horizons': horizons,
        'method': 'DIRECT_HISTORICAL_ABS_HORIZON_RETURNS_PLUS_REALIZED_AND_EWMA_VOL_DIAGNOSTICS',
    }


def geometry_fit(forecast, direction, entry, stop_loss, target, horizon_h=4):
    """Describe geometry versus empirical movement; never returns an approval gate."""
    entry = _f(entry); stop_loss = _f(stop_loss); target = _f(target)
    direction = str(direction or '').upper()
    key = str(int(horizon_h)) if float(horizon_h).is_integer() else str(float(horizon_h))
    horizon = (forecast or {}).get('horizons', {}).get(key, {})
    p80 = _f(((horizon.get('empirical_abs_move_pct') or {}).get('p80')))
    base = {
        'version': VERSION,
        'horizon_h': horizon_h,
        'direction': direction,
        'gate_mode': 'OBSERVE_ONLY',
        'can_override_production': False,
        'research_only': True,
    }
    if None in (entry, stop_loss, target) or entry <= 0 or direction not in ('LONG', 'SHORT'):
        return {**base, 'status': 'INSUFFICIENT', 'reason': 'INVALID_GEOMETRY'}
    if horizon.get('status') != 'READY' or p80 is None or p80 <= 0:
        return {**base, 'status': 'INSUFFICIENT', 'reason': 'FORECAST_HORIZON_NOT_READY'}

    if direction == 'LONG':
        reward = target - entry; risk = entry - stop_loss
    else:
        reward = entry - target; risk = stop_loss - entry
    if reward <= 0 or risk <= 0:
        return {**base, 'status': 'INSUFFICIENT', 'reason': 'DIRECTIONALLY_INVALID_GEOMETRY'}

    reward_pct = reward / entry * 100.0
    risk_pct = risk / entry * 100.0
    target_vs_p80 = reward_pct / p80
    stop_vs_p80 = risk_pct / p80
    if target_vs_p80 > 1.8:
        target_fit = 'STRETCHED_VS_EMPIRICAL_P80'
    elif target_vs_p80 < 0.45:
        target_fit = 'CLOSE_VS_EMPIRICAL_P80'
    else:
        target_fit = 'PLAUSIBLE_VS_EMPIRICAL_P80'
    if stop_vs_p80 < 0.25:
        stop_fit = 'TIGHT_VS_EMPIRICAL_P80'
    elif stop_vs_p80 > 1.4:
        stop_fit = 'WIDE_VS_EMPIRICAL_P80'
    else:
        stop_fit = 'PLAUSIBLE_VS_EMPIRICAL_P80'

    return {
        **base,
        'status': 'READY',
        'empirical_p80_abs_move_pct': round(p80, 6),
        'target_distance_pct': round(reward_pct, 6),
        'stop_distance_pct': round(risk_pct, 6),
        'target_to_p80_ratio': round(target_vs_p80, 6),
        'stop_to_p80_ratio': round(stop_vs_p80, 6),
        'target_fit': target_fit,
        'stop_fit': stop_fit,
        'approval_claimed': False,
    }
