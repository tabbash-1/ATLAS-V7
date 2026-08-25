"""ATLAS Decision Engine V7 alignment layer.

Keeps the score threshold unchanged while ensuring the execution plan uses the
same prior-structure model as Production scoring. It also exposes the strongest
available lane instead of collapsing every non-Swing setup into a generic WAIT.
"""

import production_signal_scoring as scoring
import futures_provider_chain

VERSION = 'DECISION_ENGINE_V7_BREAKOUT_AWARE'


def install(atlas):
    # Install the resilient futures chain before Production Reliability wraps
    # capture(). This keeps Binance/Kraken first, then OKX/Bybit, while HYPE can
    # still fall through to the existing Hyperliquid adapter in the outer layer.
    futures_provider_chain.install(atlas)
    original = atlas.production_decision

    def build(symbol):
        result = original(symbol)
        if not isinstance(result, dict) or not result.get('ok'):
            return result

        sym = str(result.get('symbol') or symbol or '').upper().replace('BINANCE:', '')
        direction = result.get('candidate_direction')
        px = atlas.fnum(result.get('entry'))
        indicators = result.get('indicators') or {}
        atr = atlas.fnum(indicators.get('atr14'))
        votes = int(result.get('direction_votes') or 0)
        mom24 = atlas.fnum(indicators.get('momentum_24h_pct'), 0) or 0
        paced_rv = atlas.fnum(result.get('relative_volume'), 0) or 0

        if direction in ('LONG', 'SHORT') and px and atr and atr > 0:
            ks = atlas._spot_klines(sym)
            level, distance, source = scoring.structural_obstacle(ks, px, direction)
            breakout = scoring.breakout_context(ks, px, direction, votes, mom24, atr, paced_rv)
            extension = 1.6 if breakout.get('confirmed') else 1.4
            target = level
            target_source = source
            if target is None:
                target = px + atr * extension if direction == 'LONG' else px - atr * extension
                target_source = 'ATR_EXTENSION_AFTER_CLEAR_STRUCTURE'
            stop = px - atr * 1.2 if direction == 'LONG' else px + atr * 1.2
            risk = abs(px - stop)
            reward = (target - px) if direction == 'LONG' else (px - target)
            rr = reward / risk if risk > 0 and reward > 0 else None
            directional = bool(
                rr is not None and
                ((direction == 'LONG' and stop < px < target) or
                 (direction == 'SHORT' and target < px < stop))
            )
            geometry_ok = bool(directional and rr >= 1.0)
            qualified = bool(result.get('production_signal_qualified'))

            result['stop_loss'] = round(stop, 10)
            result['take_profit'] = round(target, 10)
            result['risk_reward'] = round(rr, 3) if rr is not None else None
            result['structural_geometry'] = {
                'source': target_source,
                'obstacle_price': round(level, 10) if level is not None else None,
                'obstacle_distance_pct': round(distance, 3) if distance is not None else None,
                'breakout': breakout,
                'uses_current_candle_as_obstacle': False,
            }
            result['geometry_gate'] = {
                'status': 'PASS' if geometry_ok else 'BLOCK',
                'qualified': geometry_ok,
                'reason': 'RR_ONE_TO_ONE_OR_BETTER' if geometry_ok else 'RR_BELOW_ONE_TO_ONE' if rr is not None else 'GEOMETRY_INCOMPLETE',
                'min_risk_reward': 1.0,
                'risk_reward': round(rr, 6) if rr is not None else None,
            }
            result['execution_ready'] = bool(qualified and geometry_ok)
            result['actionable_decision'] = direction if result['execution_ready'] else 'WAIT'
            if qualified and geometry_ok:
                result['actionable_reason'] = 'EXECUTION_READY_BREAKOUT_AWARE'
                result['trade_plan_status'] = 'EXECUTION_READY'
            elif qualified:
                result['actionable_reason'] = result['geometry_gate']['reason']
                result['trade_plan_status'] = 'SCORE_QUALIFIED_GEOMETRY_BLOCKED'

            matrix = result.get('timeframe_matrix') or {}
            swing = matrix.get('swing') or {}
            swing.update({
                'risk_reward': result['risk_reward'],
                'execution_ready': result['execution_ready'],
                'actionable_decision': result['actionable_decision'],
                'structural_target_source': target_source,
                'breakout_confirmed': bool(breakout.get('confirmed')),
            })
            matrix['swing'] = swing
            result['timeframe_matrix'] = matrix

        if result.get('execution_ready') and result.get('actionable_decision') in ('LONG', 'SHORT'):
            result['best_available_action'] = {
                'action': 'BUY' if result['actionable_decision'] == 'LONG' else 'SELL',
                'direction': result['actionable_decision'],
                'lane': 'PRODUCTION_SWING',
                'status': 'ACTIONABLE',
                'entry': result.get('entry'), 'stop_loss': result.get('stop_loss'),
                'target': result.get('take_profit'), 'risk_reward': result.get('risk_reward'),
                'can_execute': False, 'research_only': True,
            }
        else:
            tactical = result.get('tactical_opportunity') or {}
            quick = result.get('quick_trade_shadow') or {}
            if tactical.get('status') in ('LONG_TACTICAL', 'SHORT_TACTICAL'):
                d = tactical.get('direction')
                result['best_available_action'] = {
                    'action': 'BUY_WATCH' if d == 'LONG' else 'SELL_WATCH', 'direction': d,
                    'lane': 'TACTICAL_1_3H', 'status': 'RESEARCH_OPPORTUNITY',
                    'entry': tactical.get('entry'), 'stop_loss': tactical.get('stop_loss'),
                    'target': tactical.get('target'), 'risk_reward': tactical.get('risk_reward'),
                    'confidence': tactical.get('confidence'), 'can_execute': False, 'research_only': True,
                }
            elif quick.get('status') == 'QUICK_TRADE_SHADOW':
                d = quick.get('direction')
                result['best_available_action'] = {
                    'action': 'BUY_WATCH' if d == 'LONG' else 'SELL_WATCH', 'direction': d,
                    'lane': 'QUICK_1_2H', 'status': 'SHADOW_OPPORTUNITY',
                    'entry': quick.get('entry'), 'stop_loss': quick.get('stop_loss'),
                    'target': quick.get('target'), 'risk_reward': quick.get('risk_reward'),
                    'confidence': quick.get('confidence'), 'can_execute': False, 'research_only': True,
                }
            else:
                result['best_available_action'] = {
                    'action': 'WAIT', 'direction': direction, 'lane': 'NONE',
                    'status': 'NO_VALID_GEOMETRY', 'can_execute': False, 'research_only': True,
                }

        result['decision_engine_version'] = VERSION
        return result

    atlas.production_decision = build
    atlas.DECISION_ENGINE_V7_STATE = {
        'enabled': True,
        'version': VERSION,
        'production_threshold_unchanged': True,
        'futures_provider_chain': futures_provider_chain.VERSION,
    }
    return atlas.DECISION_ENGINE_V7_STATE
