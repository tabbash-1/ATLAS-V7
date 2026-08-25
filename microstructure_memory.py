"""ATLAS rolling Futures microstructure memory v1.

Builds honest 4h/12h/24h context from the Smart-Money archive ATLAS already
collects roughly hourly. It never manufactures 5m/15m history from hourly data.

Open-interest changes are computed only inside the latest provider lineage for a
symbol, because OI contract units can differ across venues. Price, taker flow,
funding and book imbalance are summarized from validated snapshots only.

Research/shadow evidence only; no Production threshold or execution rule changes.
"""

from __future__ import annotations

import math
import time

VERSION = 'MICROSTRUCTURE_MEMORY_V1_PROVIDER_SAFE'
WINDOWS_HOURS = (4, 12, 24)
MIN_ROWS = {4: 3, 12: 6, 24: 12}


def _f(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _provider(row):
    return str((row or {}).get('futures_provider') or 'BINANCE_USDM_PUBLIC')


def _valid(row):
    if not isinstance(row, dict):
        return False
    if row.get('futures_evidence_validated') is False:
        return False
    return all(_f(row.get(k)) is not None for k in ('mark_price', 'open_interest', 'funding_rate', 'taker_ratio', 'orderbook_imbalance'))


def _pct(a, b):
    a = _f(a); b = _f(b)
    if a is None or b is None or a == 0:
        return None
    return (b / a - 1.0) * 100.0


def _avg(values):
    xs = [_f(x) for x in values]
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _slope(values):
    xs = [_f(x) for x in values]
    if any(x is None for x in xs) or len(xs) < 2:
        return None
    n = len(xs)
    xbar = (n - 1) / 2.0
    ybar = sum(xs) / n
    denom = sum((i - xbar) ** 2 for i in range(n))
    if denom <= 0:
        return 0.0
    return sum((i - xbar) * (y - ybar) for i, y in enumerate(xs)) / denom


def _classify(price_change, oi_change, taker, imbalance, funding):
    if None in (price_change, oi_change, taker, imbalance, funding):
        return 'INSUFFICIENT', 0

    # Strong liquidation/covering regimes are defined by price and OI moving in
    # opposite directions. These labels are descriptive, not trade signals.
    if price_change >= 0.35 and oi_change <= -0.50:
        return 'SHORT_COVERING', 72
    if price_change <= -0.35 and oi_change <= -0.50:
        return 'LONG_LIQUIDATION', 72

    long_flow = taker >= 1.05 and imbalance >= 0.03
    short_flow = taker <= 0.95 and imbalance <= -0.03
    oi_build = oi_change >= 0.50

    if price_change >= 0.25 and oi_build and long_flow:
        if funding >= 0.00035:
            return 'CROWDED_LONG_BUILDUP', 82
        return 'LONG_ACCUMULATION', 80
    if price_change <= -0.25 and oi_build and short_flow:
        if funding <= -0.00035:
            return 'CROWDED_SHORT_BUILDUP', 82
        return 'SHORT_ACCUMULATION', 80

    # Crowding can exist before price expansion; keep it visible as risk context.
    if oi_build and funding >= 0.00050 and taker >= 1.02:
        return 'CROWDED_LONG', 70
    if oi_build and funding <= -0.00050 and taker <= 0.98:
        return 'CROWDED_SHORT', 70

    if long_flow:
        return 'BUY_FLOW_BIAS', 62
    if short_flow:
        return 'SELL_FLOW_BIAS', 62
    return 'BALANCED', 55


def summarize_window(rows, hours, now_ms=None):
    now_ms = int(now_ms or time.time() * 1000)
    cutoff = now_ms - int(hours * 3600 * 1000)
    candidates = [
        r for r in rows or []
        if _valid(r) and int(r.get('captured_at_ms') or 0) >= cutoff
    ]
    candidates.sort(key=lambda r: int(r.get('captured_at_ms') or 0))
    if not candidates:
        return {
            'window_hours': hours, 'status': 'INSUFFICIENT', 'rows': 0,
            'required_rows': MIN_ROWS.get(hours, 3), 'reason': 'NO_VALIDATED_ROWS',
        }

    # OI is provider-specific. Anchor the whole usable window to the most recent
    # provider so we never compare contract counts from different exchanges.
    latest_provider = _provider(candidates[-1])
    provider_rows = [r for r in candidates if _provider(r) == latest_provider]
    required = MIN_ROWS.get(hours, 3)
    if len(provider_rows) < required:
        return {
            'window_hours': hours, 'status': 'INSUFFICIENT', 'rows': len(provider_rows),
            'validated_rows_all_providers': len(candidates), 'required_rows': required,
            'provider': latest_provider, 'reason': 'INSUFFICIENT_SAME_PROVIDER_LINEAGE',
        }

    first = provider_rows[0]
    last = provider_rows[-1]
    price_change = _pct(first.get('mark_price'), last.get('mark_price'))
    oi_change = _pct(first.get('open_interest'), last.get('open_interest'))
    taker_avg = _avg([r.get('taker_ratio') for r in provider_rows])
    imbalance_avg = _avg([r.get('orderbook_imbalance') for r in provider_rows])
    funding_avg = _avg([r.get('funding_rate') for r in provider_rows])
    taker_latest = _f(last.get('taker_ratio'))
    imbalance_latest = _f(last.get('orderbook_imbalance'))
    funding_latest = _f(last.get('funding_rate'))
    price_slope = _slope([r.get('mark_price') for r in provider_rows])
    oi_slope = _slope([r.get('open_interest') for r in provider_rows])

    long_flow_fraction = sum(
        1 for r in provider_rows
        if _f(r.get('taker_ratio'), 1.0) >= 1.05 and _f(r.get('orderbook_imbalance'), 0.0) >= 0.03
    ) / len(provider_rows)
    short_flow_fraction = sum(
        1 for r in provider_rows
        if _f(r.get('taker_ratio'), 1.0) <= 0.95 and _f(r.get('orderbook_imbalance'), 0.0) <= -0.03
    ) / len(provider_rows)

    label, confidence = _classify(price_change, oi_change, taker_avg, imbalance_avg, funding_avg)
    age_minutes = (now_ms - int(last.get('captured_at_ms') or 0)) / 60000.0
    stale = age_minutes > 120
    if stale:
        confidence = min(confidence, 35)

    return {
        'window_hours': hours,
        'status': 'STALE' if stale else 'READY',
        'rows': len(provider_rows),
        'validated_rows_all_providers': len(candidates),
        'required_rows': required,
        'provider': latest_provider,
        'provider_lineage_safe': True,
        'first_ms': int(first.get('captured_at_ms') or 0),
        'last_ms': int(last.get('captured_at_ms') or 0),
        'age_minutes': round(age_minutes, 2),
        'price_change_pct': round(price_change, 6) if price_change is not None else None,
        'open_interest_change_pct': round(oi_change, 6) if oi_change is not None else None,
        'taker_ratio_avg': round(taker_avg, 6) if taker_avg is not None else None,
        'taker_ratio_latest': taker_latest,
        'orderbook_imbalance_avg': round(imbalance_avg, 6) if imbalance_avg is not None else None,
        'orderbook_imbalance_latest': imbalance_latest,
        'funding_rate_avg': round(funding_avg, 8) if funding_avg is not None else None,
        'funding_rate_latest': funding_latest,
        'long_flow_fraction': round(long_flow_fraction, 4),
        'short_flow_fraction': round(short_flow_fraction, 4),
        'price_slope_per_sample': round(price_slope, 8) if price_slope is not None else None,
        'oi_slope_per_sample': round(oi_slope, 8) if oi_slope is not None else None,
        'label': label,
        'confidence': confidence,
        'research_only': True,
    }


def analyze(symbol, archive_rows, now_ms=None):
    normalized = str(symbol or '').upper().replace('BINANCE:', '')
    symbol_rows = [r for r in archive_rows or [] if str(r.get('symbol') or '').upper().replace('BINANCE:', '') == normalized]
    windows = {str(h): summarize_window(symbol_rows, h, now_ms=now_ms) for h in WINDOWS_HOURS}

    ready = [w for w in windows.values() if w.get('status') == 'READY']
    labels = [w.get('label') for w in ready]
    bullish = {'LONG_ACCUMULATION', 'BUY_FLOW_BIAS'}
    bearish = {'SHORT_ACCUMULATION', 'SELL_FLOW_BIAS'}
    long_risk = {'CROWDED_LONG', 'CROWDED_LONG_BUILDUP'}
    short_risk = {'CROWDED_SHORT', 'CROWDED_SHORT_BUILDUP'}

    bullish_votes = sum(1 for x in labels if x in bullish)
    bearish_votes = sum(1 for x in labels if x in bearish)
    long_crowding_votes = sum(1 for x in labels if x in long_risk)
    short_crowding_votes = sum(1 for x in labels if x in short_risk)

    if bullish_votes >= 2:
        consensus = 'BULLISH_FLOW'
    elif bearish_votes >= 2:
        consensus = 'BEARISH_FLOW'
    elif long_crowding_votes >= 2:
        consensus = 'LONG_CROWDING_RISK'
    elif short_crowding_votes >= 2:
        consensus = 'SHORT_CROWDING_RISK'
    elif len(ready) >= 2:
        consensus = 'MIXED'
    else:
        consensus = 'INSUFFICIENT'

    return {
        'version': VERSION,
        'symbol': normalized,
        'sampling_contract': 'HOURLY_ARCHIVE_ONLY_NO_FAKE_INTRABAR_MEMORY',
        'windows': windows,
        'ready_windows': len(ready),
        'consensus': consensus,
        'bullish_flow_votes': bullish_votes,
        'bearish_flow_votes': bearish_votes,
        'long_crowding_votes': long_crowding_votes,
        'short_crowding_votes': short_crowding_votes,
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
    }
