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


def test_strong_broad_rally_is_evidence_only_and_cannot_clear_structure_penalty():
    atlas = FakeAtlas()
    continuation.install(atlas)
    row = atlas.cloud_score_symbol('BTCUSDT', atlas._spot_klines('BTCUSDT'))
    assert row['continuation_context']['strong'] is True, row
    assert row['score_attribution']['obstacle_adjustment_before_continuation'] == -8
    assert row['score_attribution']['obstacle_adjustment'] == -8
    assert row['score_attribution']['continuation_obstacle_relief'] == 0
    assert row['score_attribution']['continuation_obstacle_reason'] == 'EVIDENCE_ONLY_NO_STRUCTURE_RELIEF'
    assert row['structural_target_source'] == 'PRIOR_SWING_HIGH'
    assert atlas.PRODUCTION_CONTINUATION_SCORING_STATE['continuation_evidence_only'] is True
    assert atlas.PRODUCTION_CONTINUATION_SCORING_STATE['can_relieve_structure_penalty'] is False
    assert atlas.PRODUCTION_CONTINUATION_SCORING_STATE['can_extend_structural_target'] is False

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


class PartialCandleShockAtlas(FakeAtlas):
    @staticmethod
    def _rsi(values, period):
        # If the live shock leaks into continuation authority this returns blowoff.
        return 86.0 if values and values[-1] > 200 else 70.0

    @staticmethod
    def _spot_klines(symbol):
        rows = []
        for i in range(60):
            px = 100 + i * 0.25
            rows.append({'open': px-0.1, 'high': px+0.2, 'low': px-0.2, 'close': px, 'volume': 100})
        # Still-forming 1H candle: extreme spike that must be ignored by breadth/RSI authority.
        rows.append({'open': 114.75, 'high': 320.0, 'low': 114.5, 'close': 300.0, 'volume': 5000})
        return rows


def test_market_breadth_ignores_still_forming_1h_candle():
    atlas = PartialCandleShockAtlas()
    breadth = continuation._compute_breadth(atlas)
    assert breadth['available'] == len(atlas.ON_DEMAND_SYMBOLS)
    assert breadth['long_count'] == len(atlas.ON_DEMAND_SYMBOLS)
    assert breadth['long_fraction'] == 1.0


def test_continuation_rsi_ignores_still_forming_1h_candle():
    atlas = PartialCandleShockAtlas()
    continuation.install(atlas)
    row = atlas.cloud_score_symbol('BTCUSDT', atlas._spot_klines('BTCUSDT'))
    assert row['score_attribution']['extension_guard_adjustment'] == 0
    assert row['score_attribution']['extension_guard_reason'] == 'RSI_SANE'
    assert row['continuation_context']['rsi_sane'] is True
    assert atlas.PRODUCTION_CONTINUATION_SCORING_STATE['closed_candle_authority'] is True
    assert atlas.PRODUCTION_CONTINUATION_SCORING_STATE['live_1h_can_change_continuation_state'] is False


class NoDirectionAtlas(FakeAtlas):
    @staticmethod
    def _base_score(symbol, btc_ks):
        return {
            'symbol': symbol,
            'direction': None,
            'final_score': 61,
            'production_signal_qualified': False,
            'scoring_version': 'PROD_SIGNAL_SCORING_V13_EVENT_TIME_BREAKOUT',
        }


def test_no_direction_wait_still_publishes_continuation_provenance():
    atlas = NoDirectionAtlas()
    continuation.install(atlas)
    row = atlas.cloud_score_symbol('SOLUSDT', atlas._spot_klines('SOLUSDT'))
    assert row['direction'] is None
    assert row['production_signal_qualified'] is False
    assert row['continuation_scoring_version'] == continuation.VERSION
    assert row['continuation_context']['status'] == 'NOT_APPLICABLE'
    assert row['continuation_context']['strong'] is False
    assert row['continuation_context']['can_promote_trade'] is False
    assert row['market_breadth'] is None


def test_momentum_tiers_are_monotonic_but_bounded():
    assert continuation.momentum_adjustment('LONG', 1.0, 60) == 0
    assert continuation.momentum_adjustment('LONG', 2.0, 60) == 2
    assert continuation.momentum_adjustment('LONG', 4.0, 60) == 4
    assert continuation.momentum_adjustment('LONG', 8.0, 60) == 6
    assert continuation.momentum_adjustment('SHORT', -4.0, 40) == 4


if __name__ == '__main__':
    test_strong_broad_rally_is_evidence_only_and_cannot_clear_structure_penalty()
    test_weak_breadth_does_not_relieve_obstacle()
    test_blowoff_rsi_blocks_momentum_bonus_and_continuation_relief()
    test_market_breadth_ignores_still_forming_1h_candle()
    test_continuation_rsi_ignores_still_forming_1h_candle()
    test_no_direction_wait_still_publishes_continuation_provenance()
    test_momentum_tiers_are_monotonic_but_bounded()
    print('production continuation scoring tests: ok')
