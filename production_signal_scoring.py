"""ATLAS production signal scoring v6.

V6 fixes two decision-engine blind spots without weakening the Production
threshold: current/incomplete candles are no longer allowed to masquerade as a
fresh resistance/support obstacle, and partial-hour volume is normalized by
candle progress. Breakout/continuation geometry is built from prior structure
rather than the current candle's own high/low.
"""

import time

VERSION = "PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE+PARTIAL_VOLUME_TIME_FIX_V1"
LOOKBACK_BARS = 96
RANGE_BARS = 24


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def candle_progress(row, now_ms=None):
    """Return elapsed fraction of the current 1h candle, bounded for stability.

    ``collector_server._spot_klines`` exposes Binance's candle open timestamp as
    ``time``. Older/test callers may use ``open_time``. Supporting both keeps the
    intended partial-hour normalization active in live Production without
    changing completed-candle behavior.
    """
    r = row or {}
    open_ms = int(r.get('open_time') or r.get('time') or 0)
    if not open_ms:
        return 1.0
    now_ms = int(now_ms or time.time() * 1000)
    elapsed = max(0, now_ms - open_ms)
    return max(0.10, min(1.0, elapsed / 3600000.0))


def paced_relative_volume(raw_rv, progress):
    raw = max(0.0, _f(raw_rv, 0.0))
    p = max(0.10, min(1.0, _f(progress, 1.0)))
    return min(4.0, raw / p)


def prior_range(ks, bars=RANGE_BARS):
    prior = list(ks or [])[-(bars + 1):-1]
    if not prior:
        return None, None
    highs = [_f(x.get('high')) for x in prior]
    lows = [_f(x.get('low')) for x in prior]
    highs = [x for x in highs if x is not None]
    lows = [x for x in lows if x is not None]
    return (max(highs) if highs else None, min(lows) if lows else None)


def structural_obstacle(ks, px, direction):
    """Nearest prior swing obstacle, explicitly excluding the current candle."""
    prior = list(ks or [])[-(LOOKBACK_BARS + 1):-1]
    swings = []
    for i in range(2, len(prior) - 2):
        row = prior[i]
        if direction == 'LONG':
            v = _f(row.get('high'))
            if v is not None and v >= _f(prior[i-1].get('high'), v) and v >= _f(prior[i+1].get('high'), v):
                swings.append(v)
        else:
            v = _f(row.get('low'))
            if v is not None and v <= _f(prior[i-1].get('low'), v) and v <= _f(prior[i+1].get('low'), v):
                swings.append(v)

    min_room = 0.0015
    if direction == 'LONG':
        candidates = sorted({v for v in swings if v > px * (1 + min_room)})
        if candidates:
            level = candidates[0]
            return level, (level / px - 1) * 100, 'PRIOR_SWING_HIGH'
        prior_high, _ = prior_range(ks)
        if prior_high is not None and prior_high > px * (1 + min_room):
            return prior_high, (prior_high / px - 1) * 100, 'PRIOR_RANGE_HIGH'
        return None, None, 'NO_PRIOR_RESISTANCE_AHEAD'

    candidates = sorted({v for v in swings if v < px * (1 - min_room)}, reverse=True)
    if candidates:
        level = candidates[0]
        return level, (px / level - 1) * 100, 'PRIOR_SWING_LOW'
    _, prior_low = prior_range(ks)
    if prior_low is not None and prior_low < px * (1 - min_room):
        return prior_low, (px / prior_low - 1) * 100, 'PRIOR_RANGE_LOW'
    return None, None, 'NO_PRIOR_SUPPORT_AHEAD'


def breakout_context(ks, px, direction, votes, mom24, atr, paced_rv):
    high24, low24 = prior_range(ks)
    current = (ks or [{}])[-1]
    op = _f(current.get('open'), px)
    body_atr = abs(px - op) / atr if atr else 0.0
    if direction == 'LONG':
        beyond = high24 is not None and px > high24
        momentum_ok = mom24 > 0
    else:
        beyond = low24 is not None and px < low24
        momentum_ok = mom24 < 0
    confirmed = bool(beyond and votes == 4 and momentum_ok and (paced_rv >= 0.80 or body_atr >= 0.35))
    return {
        'confirmed': confirmed,
        'beyond_prior_24h_range': bool(beyond),
        'prior_24h_high': high24,
        'prior_24h_low': low24,
        'current_body_atr': round(body_atr, 4),
        'paced_relative_volume': round(paced_rv, 3),
        'confirmation_rule': '4_VOTES_AND_RANGE_BREAK_AND_(RV_PACE>=0.8_OR_BODY>=0.35ATR)',
    }


def obstacle_adjustment(distance_pct, source, breakout_confirmed):
    if breakout_confirmed and distance_pct is None:
        return 3, 'CONFIRMED_BREAKOUT_CLEAR_SPACE'
    if distance_pct is None:
        return 0, 'NO_PRIOR_OBSTACLE_AHEAD'
    if distance_pct < .7:
        return -8, 'VERY_CLOSE_PRIOR_STRUCTURE'
    if distance_pct < 1.4:
        return -4, 'CLOSE_PRIOR_STRUCTURE'
    if distance_pct > 2.5:
        return 3, 'CLEAR_SPACE_TO_PRIOR_STRUCTURE'
    return 0, 'ACCEPTABLE_PRIOR_STRUCTURE'


def install(atlas):
    def cloud_score_symbol_v6(symbol, btc_ks):
        ks = atlas._spot_klines(symbol)
        if len(ks) < 100:
            return None

        closes = [x['close'] for x in ks]
        vols = [x['volume'] for x in ks]
        px = closes[-1]
        ema20 = atlas._ema(closes[-80:], 20)
        ema50 = atlas._ema(closes[-120:], 50)
        rsi = atlas._rsi(closes, 14)
        atr = atlas._atr(ks, 14)
        if not px or not ema20 or not ema50 or not atr or atr <= 0:
            return None

        vol_base = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else vols[-1]
        raw_rv = vols[-1] / vol_base if vol_base else 1.0
        progress = candle_progress(ks[-1])
        rv = paced_relative_volume(raw_rv, progress)
        sup, res, sd, rd = atlas._cloud_sr(ks)
        rel = 50.0 if symbol == 'BTCUSDT' else atlas._cloud_relative(ks, btc_ks)
        mom24 = ((px / closes[-25]) - 1) * 100 if len(closes) >= 25 and closes[-25] else 0.0

        long_votes = sum((px >= ema20, ema20 >= ema50, rsi >= 50, mom24 >= 0))
        short_votes = sum((px <= ema20, ema20 <= ema50, rsi <= 50, mom24 <= 0))
        if max(long_votes, short_votes) < 3 or long_votes == short_votes:
            return None
        direction = 'LONG' if long_votes > short_votes else 'SHORT'
        votes = long_votes if direction == 'LONG' else short_votes

        snap = {}
        futures_available = False
        try:
            snap = atlas.capture(symbol) or {}
            futures_available = bool(
                snap.get('futures_evidence_validated',
                         (snap.get('futures_provider') or 'BINANCE_USDM_PUBLIC') == 'BINANCE_USDM_PUBLIC')
            )
        except Exception:
            snap = {}

        raw_fscore = atlas.fnum(snap.get('experimental_score'))
        raw_funding = atlas.fnum(snap.get('funding_rate'))
        raw_oi = atlas.fnum(snap.get('oi_change_pct'))
        raw_taker = atlas.fnum(snap.get('taker_ratio'))
        raw_book = atlas.fnum(snap.get('orderbook_imbalance'))
        fscore = raw_fscore if futures_available and raw_fscore is not None else 0
        funding = raw_funding if futures_available and raw_funding is not None else 0
        oi = raw_oi if futures_available and raw_oi is not None else 0
        taker = raw_taker if futures_available and raw_taker is not None else 1
        book = raw_book if futures_available and raw_book is not None else 0

        trend_base = 60 + (8 if votes == 4 else 4)
        volume_bonus = min(10, max(0, (rv - 1) * 10))

        relative_strength_adjustment = 0
        relative_strength_reason = 'NEUTRAL'
        if (direction == 'LONG' and rel >= 60) or (direction == 'SHORT' and rel <= 40):
            relative_strength_adjustment = 6
            relative_strength_reason = 'ALIGNED_STRONG'
        elif (direction == 'LONG' and rel <= 35) or (direction == 'SHORT' and rel >= 65):
            relative_strength_adjustment = -5
            relative_strength_reason = 'OPPOSED_STRONG'

        futures_adjustment = 0
        futures_reason = 'NOT_AVAILABLE'
        if futures_available:
            aligned = (direction == 'LONG' and fscore > 0) or (direction == 'SHORT' and fscore < 0)
            magnitude = min(8, abs(fscore) * .10)
            futures_adjustment = magnitude if aligned else -magnitude
            futures_reason = 'ALIGNED' if aligned else 'OPPOSED'
        elif raw_fscore is not None:
            futures_reason = 'SHADOW_ONLY_UNVALIDATED_PROVIDER'

        level, obstacle, obstacle_source = structural_obstacle(ks, px, direction)
        breakout = breakout_context(ks, px, direction, votes, mom24, atr, rv)
        obstacle_adj, obstacle_reason = obstacle_adjustment(obstacle, obstacle_source, breakout['confirmed'])

        raw_score = trend_base + volume_bonus + relative_strength_adjustment + futures_adjustment + obstacle_adj
        score = round(max(0, min(100, raw_score)))
        signal_threshold = float(atlas.CLOUD_FORWARD_MIN_SCORE)
        production_signal_qualified = bool(score >= signal_threshold)
        research_champion_take = bool(score >= 60)

        if direction == 'LONG' and oi >= 3 and funding >= .00035 and rv < 1 and obstacle is not None and obstacle <= 2:
            pb = 'LEVERAGE_TRAP_LONG_RISK'
        elif direction == 'SHORT' and oi >= 3 and funding <= -.00035 and rv < 1 and obstacle is not None and obstacle <= 2:
            pb = 'LEVERAGE_TRAP_SHORT_RISK'
        elif breakout['confirmed'] and direction == 'LONG':
            pb = 'BREAKOUT_CONFIRMED_LONG'
        elif breakout['confirmed'] and direction == 'SHORT':
            pb = 'BREAKDOWN_CONFIRMED_SHORT'
        elif direction == 'LONG' and rv >= 1.2:
            pb = 'BREAKOUT_CONTINUATION_LONG'
        elif direction == 'SHORT' and rv >= 1.2:
            pb = 'BREAKDOWN_CONTINUATION_SHORT'
        else:
            pb = 'TREND_PULLBACK_LONG' if direction == 'LONG' else 'TREND_PULLBACK_SHORT'

        risk = atr * 1.2
        if level is not None:
            target = level
            target_source = obstacle_source
        else:
            extension = 1.6 if breakout['confirmed'] else 1.4
            target = px + atr * extension if direction == 'LONG' else px - atr * extension
            target_source = 'ATR_EXTENSION_AFTER_CLEAR_STRUCTURE'
        reward = (target - px) if direction == 'LONG' else (px - target)
        rr = (reward / risk) if risk > 0 and reward > 0 else None

        attribution = {
            'trend_base': round(trend_base, 3),
            'volume_bonus': round(volume_bonus, 3),
            'relative_strength_adjustment': round(relative_strength_adjustment, 3),
            'relative_strength_reason': relative_strength_reason,
            'futures_adjustment': round(futures_adjustment, 3),
            'futures_reason': futures_reason,
            'obstacle_adjustment': round(obstacle_adj, 3),
            'obstacle_reason': obstacle_reason,
            'obstacle_distance_pct': round(obstacle, 3) if obstacle is not None else None,
            'obstacle_source': obstacle_source,
            'raw_score': round(raw_score, 3),
            'final_score': score,
            'formula': 'trend_base + paced_volume_bonus + relative_strength_adjustment + futures_adjustment + prior_structure_obstacle_adjustment',
        }

        return {
            'symbol': symbol, 'direction': direction, 'entry': px,
            'champion_score': score, 'champion_take': research_champion_take,
            'research_champion_take': research_champion_take,
            'production_signal_qualified': production_signal_qualified,
            'signal_threshold': signal_threshold,
            'final_score': score, 'opportunity_score': score,
            'execution_decision': f'{direction}_CANDIDATE' if production_signal_qualified else f'{direction}_WATCH',
            'trade_plan_status': 'PLAN_READY' if rr is not None else 'INCOMPLETE',
            'rr_tp1': None, 'rr_tp2': round(rr, 3) if rr is not None else None,
            'anomaly_score': None, 'portfolio_allowed': None,
            'futures_available': futures_available, 'futures_provider': snap.get('futures_provider'),
            'futures_score': fscore if futures_available else None,
            'futures_shadow_score': raw_fscore, 'futures_shadow_provider': snap.get('futures_provider'),
            'futures_shadow_validated': futures_available,
            'futures_shadow_only': bool(raw_fscore is not None and not futures_available),
            'liquidity_score': None,
            'volume_quality': round(max(0, min(100, 45 + (rv - 1) * 35)), 2),
            'relative_volume': round(rv, 3),
            'relative_volume_raw': round(raw_rv, 3),
            'current_candle_progress': round(progress, 3),
            'funding_rate': funding, 'oi_change_pct': oi, 'taker_ratio': taker, 'orderbook_imbalance': book,
            'futures_shadow_funding_rate': raw_funding, 'futures_shadow_oi_change_pct': raw_oi,
            'futures_shadow_taker_ratio': raw_taker, 'futures_shadow_orderbook_imbalance': raw_book,
            'relative_strength_score': round(rel, 2),
            'regime': 'BREAKOUT_UP' if breakout['confirmed'] and direction == 'LONG' else 'BREAKDOWN_DOWN' if breakout['confirmed'] else 'TREND_UP' if direction == 'LONG' else 'TREND_DOWN',
            'support_strength': 60, 'support_distance_pct': round(sd, 3) if sd is not None else None,
            'resistance_strength': 60, 'resistance_distance_pct': round(rd, 3) if rd is not None else None,
            'structural_obstacle_price': round(level, 10) if level is not None else None,
            'structural_obstacle_source': obstacle_source,
            'structural_target': round(target, 10) if target is not None else None,
            'structural_target_source': target_source,
            'breakout_context': breakout,
            'playbook_primary': pb, 'playbook_score': score, 'playbook_all': [pb, VERSION],
            'direction_votes': votes, 'direction_votes_long': long_votes, 'direction_votes_short': short_votes,
            'momentum_24h_pct': round(mom24, 3), 'score_attribution': attribution,
            'scoring_version': VERSION, 'auto_source': 'CLOUD_FORWARD_ALPHA18', 'dedup_minutes': 50,
        }

    atlas.cloud_score_symbol = cloud_score_symbol_v6
    return atlas.cloud_score_symbol