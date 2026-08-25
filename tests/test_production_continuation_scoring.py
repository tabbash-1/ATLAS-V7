#!/usr/bin/env python3
import math
import production_continuation_scoring as continuation


class FakeAtlas:
    ON_DEMAND_SYMBOLS = ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT')
    CLOUD_FORWARD_MIN_SCORE = 68

    def __init__(self):
        self.cloud_score_symbol = self._base_score

    @staticmethod
    def _ema(values, period):
        vals = list(values)[-period:]
        return sum(vals) / len(vals)

    @staticmethod
    def _rsi(values, period):
        return 70.0

    @staticmethod
    def _atr(ks, period):
        return 1.0

    @staticmethod
    def _base_score(symbol, btc_ks):
        return {
            'symbol': symbol,
            'direction': 'LONG',
            'entry': 114.75,
            'direction_votes': 4,
            'momentum_24h_pct': 5.2,
            'structural_obstacle_price': 115.3,
            'structural_target': 115.3,
            'structural_target_source': 'PRIOR_SWING_HIGH',
            'rr_tp2': 0.458,
            'champion_score': 60,
            'final_score': 60,
            'opportunity_score': 60,
            'production_signal_qualified': False,
            'research_champion_take': True,
            'champion_take': True,
            'execution_decision': 'LONG_WATCH',
            'playbook_score': 60,
            'playbook_primary': 'TREND_PULLBACK_LONG',
            'scoring_version': 'PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE',
            'score_attribution': {
                'trend_base': 68,
                'volume_bonus': 0,
                'relative_strength_adjustment': 0,
                'futures_adjustment': 0,
                'obstacle_adjustment': -8,
                'obstacle_distance_pct': 0.479,
                'raw_score': 60,
                'final_score': 60,
            },
        }

    @staticmethod
    def _spot_klines(symbol):
        rows = []
        for i in range(60):
            px = 100 + i * 0.25
            rows.append({'open': px-0.1, 'high': px+0.2, 'low': px-0.2, 'close': px, 'volume': 100})
        return rows


def test_strong_broad_rally_can_clear_excessive_obstacle_penalty():
    atlas = FakeAtlas()
    continuation.install(atlas)
    row = atlas.cloud_score_symbol('BTCUSDT', atlas._spot_klines('BTCUSDT'))
    assert row['continuation_context']['strong'] is True, row
    assert row['score_attribution']['obstacle_adjustment_before_continuation'] == -8
    assert row['score_attribution']['obstacle_adjustment'] == -3
    assert row['score_attribution']['momentum_adjustment'] == 6
    assert row['score_attribution']['market_breadth_adjustment'] == 3
    assert row['final_score'] >= 68, row
    assert row['production_signal_qualified'] is True
    assert row['structural_target_source'] == 'CONTINUATION_EXTENSION_BEYOND_PRIOR_STRUCTURE'
    assert row['structural_target'] > row['structural_obstacle_price']
    assert row['rr_tp2'] > 1.0


def test_weak_breadth_does_not_relieve_obstacle():
    breadth = {'available': 8, 'long_fraction': 0.375, 'short_fraction': 0.25}
    ctx = continuation.continuation_context('LONG', 4, 5.0, 70, breadth)
    assert ctx['strong'] is False
    adjusted, relief, reason = continuation.relieved_obstacle_adjustment(-8, ctx['strong'])
    assert adjusted == -8
    assert relief == 0
    assert reason == 'UNCHANGED'
    assert continuation.breadth_adjustment('LONG', breadth) == 0


def test_blowoff_rsi_blocks_momentum_bonus_and_continuation_relief():
    breadth = {'available': 8, 'long_fraction': 1.0, 'short_fraction': 0.0}
    assert continuation.momentum_adjustment('LONG', 7.0, 86) == 0
    guard, reason = continuation.extension_guard_adjustment('LONG', 86)
    assert guard == -4
    assert reason == 'BLOWOFF_RSI_LONG'
    ctx = continuation.continuation_context('LONG', 4, 7.0, 86, breadth)
    assert ctx['strong'] is False
    adjusted, relief, _ = continuation.relieved_obstacle_adjustment(-8, ctx['strong'])
    assert adjusted == -8 and relief == 0


def test_momentum_tiers_are_monotonic_but_bounded():
    assert continuation.momentum_adjustment('LONG', 1.0, 60) == 0
    assert continuation.momentum_adjustment('LONG', 2.0, 60) == 2
    assert continuation.momentum_adjustment('LONG', 4.0, 60) == 4
    assert continuation.momentum_adjustment('LONG', 8.0, 60) == 6
    assert continuation.momentum_adjustment('SHORT', -4.0, 40) == 4


if __name__ == '__main__':
    test_strong_broad_rally_can_clear_excessive_obstacle_penalty()
    test_weak_breadth_does_not_relieve_obstacle()
    test_blowoff_rsi_blocks_momentum_bonus_and_continuation_relief()
    test_momentum_tiers_are_monotonic_but_bounded()
    print('production continuation scoring tests: ok')
