"""ATLAS production signal scoring v5.

Keeps the graded four-vote production decision model and exact score
attribution. Production score qualification is emitted explicitly and remains
separate from the broader research champion lane. Provider-specific derivatives
fallbacks may be surfaced as shadow context, but they never affect Production
unless futures_evidence_validated is true.
"""

VERSION = "PROD_SIGNAL_SCORING_V5_FUTURES_SHADOW_CONTEXT"


def install(atlas):
    def cloud_score_symbol_v5(symbol, btc_ks):
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
        rv = vols[-1] / vol_base if vol_base else 1.0
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

        # Preserve provider-specific derivatives context for Research even when
        # it is not validated for Production. Only validated data can contribute
        # to Production's futures adjustment.
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

        # Exact additive score attribution. Weak volume is not a penalty in this
        # model; it simply earns no positive volume bonus.
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

        obstacle = rd if direction == 'LONG' else sd
        obstacle_adjustment = 0
        obstacle_reason = 'NO_OBSTACLE_DATA'
        if obstacle is not None:
            if obstacle < .7:
                obstacle_adjustment = -8
                obstacle_reason = 'VERY_CLOSE'
            elif obstacle < 1.4:
                obstacle_adjustment = -4
                obstacle_reason = 'CLOSE'
            elif obstacle > 2.5:
                obstacle_adjustment = 3
                obstacle_reason = 'CLEAR_SPACE'
            else:
                obstacle_reason = 'ACCEPTABLE'

        raw_score = (
            trend_base
            + volume_bonus
            + relative_strength_adjustment
            + futures_adjustment
            + obstacle_adjustment
        )
        score = round(max(0, min(100, raw_score)))
        signal_threshold = float(atlas.CLOUD_FORWARD_MIN_SCORE)
        production_signal_qualified = bool(score >= signal_threshold)
        research_champion_take = bool(score >= 60)

        attribution = {
            'trend_base': round(trend_base, 3),
            'volume_bonus': round(volume_bonus, 3),
            'relative_strength_adjustment': round(relative_strength_adjustment, 3),
            'relative_strength_reason': relative_strength_reason,
            'futures_adjustment': round(futures_adjustment, 3),
            'futures_reason': futures_reason,
            'obstacle_adjustment': round(obstacle_adjustment, 3),
            'obstacle_reason': obstacle_reason,
            'obstacle_distance_pct': round(obstacle, 3) if obstacle is not None else None,
            'raw_score': round(raw_score, 3),
            'final_score': score,
            'formula': 'trend_base + volume_bonus + relative_strength_adjustment + futures_adjustment + obstacle_adjustment',
        }

        if direction == 'LONG' and oi >= 3 and funding >= .00035 and rv < 1 and rd is not None and rd <= 2:
            pb = 'LEVERAGE_TRAP_LONG_RISK'
        elif direction == 'SHORT' and oi >= 3 and funding <= -.00035 and rv < 1 and sd is not None and sd <= 2:
            pb = 'LEVERAGE_TRAP_SHORT_RISK'
        elif direction == 'LONG' and rv >= 1.2:
            pb = 'BREAKOUT_CONTINUATION_LONG'
        elif direction == 'SHORT' and rv >= 1.2:
            pb = 'BREAKDOWN_CONTINUATION_SHORT'
        else:
            pb = 'TREND_PULLBACK_LONG' if direction == 'LONG' else 'TREND_PULLBACK_SHORT'

        risk = atr * 1.2
        reward = ((res - px) if direction == 'LONG' and res is not None
                  else (px - sup) if direction == 'SHORT' and sup is not None
                  else None)
        rr = (reward / risk) if reward is not None and risk > 0 and reward > 0 else None

        return {
            'symbol': symbol, 'direction': direction, 'entry': px,
            'champion_score': score,
            'champion_take': research_champion_take,
            'research_champion_take': research_champion_take,
            'production_signal_qualified': production_signal_qualified,
            'signal_threshold': signal_threshold,
            'final_score': score, 'opportunity_score': score,
            'execution_decision': f'{direction}_CANDIDATE' if production_signal_qualified else f'{direction}_WATCH',
            'trade_plan_status': 'PLAN_READY' if rr is not None else 'INCOMPLETE',
            'rr_tp1': None, 'rr_tp2': round(rr, 3) if rr is not None else None,
            'anomaly_score': None, 'portfolio_allowed': None,
            'futures_available': futures_available,
            'futures_provider': snap.get('futures_provider'),
            'futures_score': fscore if futures_available else None,
            'futures_shadow_score': raw_fscore,
            'futures_shadow_provider': snap.get('futures_provider'),
            'futures_shadow_validated': futures_available,
            'futures_shadow_only': bool(raw_fscore is not None and not futures_available),
            'liquidity_score': None,
            'volume_quality': round(max(0, min(100, 45 + (rv - 1) * 35)), 2),
            'relative_volume': round(rv, 3),
            'funding_rate': funding, 'oi_change_pct': oi,
            'taker_ratio': taker, 'orderbook_imbalance': book,
            'futures_shadow_funding_rate': raw_funding,
            'futures_shadow_oi_change_pct': raw_oi,
            'futures_shadow_taker_ratio': raw_taker,
            'futures_shadow_orderbook_imbalance': raw_book,
            'relative_strength_score': round(rel, 2),
            'regime': 'TREND_UP' if direction == 'LONG' else 'TREND_DOWN',
            'support_strength': 60,
            'support_distance_pct': round(sd, 3) if sd is not None else None,
            'resistance_strength': 60,
            'resistance_distance_pct': round(rd, 3) if rd is not None else None,
            'playbook_primary': pb, 'playbook_score': score, 'playbook_all': [pb, VERSION],
            'direction_votes': votes,
            'direction_votes_long': long_votes,
            'direction_votes_short': short_votes,
            'momentum_24h_pct': round(mom24, 3),
            'score_attribution': attribution,
            'scoring_version': VERSION,
            'auto_source': 'CLOUD_FORWARD_ALPHA18', 'dedup_minutes': 50,
        }

    atlas.cloud_score_symbol = cloud_score_symbol_v5
    return atlas.cloud_score_symbol
