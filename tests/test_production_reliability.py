#!/usr/bin/env python3
import math
import production_reliability as reliability


class FakeAtlas:
    ON_DEMAND_SYMBOLS = ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT')
    UA = 'ATLAS-test'

    @staticmethod
    def fnum(value, default=None):
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def now_iso():
        return '2026-08-24T21:00:00+00:00'

    @staticmethod
    def orderbook_metrics(depth):
        bids = depth.get('bids', [])[:20]
        asks = depth.get('asks', [])[:20]
        bidn = sum(float(p) * float(q) for p, q, *_ in bids)
        askn = sum(float(p) * float(q) for p, q, *_ in asks)
        den = bidn + askn
        return bidn, askn, ((bidn - askn) / den if den else 0.0)

    @staticmethod
    def liquidity_walls(depth, mark, top_n=5):
        return {'bid_walls': [], 'ask_walls': []}

    @staticmethod
    def score_snapshot(funding, taker, book, oi_change):
        return 7

    @staticmethod
    def previous_provider(symbol, provider):
        return None


def test_integrity_quality_separates_maturity_and_coverage():
    atlas = FakeAtlas()
    now_ms = 1787605200000
    forward = [
        {'symbol':'BTCUSDT','direction':'LONG','entry':100+i,'captured_at_ms':now_ms-(i+1)*3600000}
        for i in range(19)
    ]
    smart = [
        {'symbol':'BTCUSDT','captured_at_ms':now_ms-1000,'futures_provider':'BINANCE_USDM_PUBLIC','futures_evidence_validated':True},
        {'symbol':'ETHUSDT','captured_at_ms':now_ms-1000,'futures_provider':'BINANCE_USDM_PUBLIC','futures_evidence_validated':True},
    ]
    atlas.read_forward = lambda: forward
    atlas.read_all = lambda: smart

    old = lambda: {'quality_score':40,'status':'DEGRADED','issues':['insufficient forward sample','insufficient core coverage']}
    result = reliability._integrity_quality(atlas, old)

    assert result['quality_score'] == 100, result
    assert result['status'] == 'HEALTHY', result
    assert result['quality_scope'] == 'DATA_INTEGRITY_ONLY', result
    assert result['evidence_maturity'] == 'COLLECTING', result
    assert result['evidence_forward_rows'] == 19, result
    assert result['smart_money_coverage_status'] == 'WARMING', result
    assert 'SOLUSDT' in result['smart_money_missing_fresh_assets'], result
    assert result['issues'] == [], result


def test_conditional_wait_keeps_production_gate_unchanged():
    atlas = FakeAtlas()
    decision = {
        'ok': True,
        'symbol': 'BTCUSDT',
        'candidate_direction': 'LONG',
        'decision': 'WAIT',
        'actionable_decision': 'WAIT',
        'signal_qualified': False,
        'production_signal_qualified': False,
        'score': 66,
        'signal_threshold': 68,
        'entry': 100.0,
        'relative_strength_score': 60,
        'relative_volume': 0.5,
        'direction_votes_long': 4,
        'direction_votes_short': 0,
        'futures_score': None,
        'futures_shadow_score': None,
        'score_attribution': {'trend_base':68,'volume_bonus':0,'relative_strength_adjustment':6,'futures_adjustment':0,'obstacle_adjustment':-8,'obstacle_distance_pct':0.2},
        'tactical_opportunity': {'direction':'LONG','entry':100.0,'target':101.0,'stop_loss':99.35,'risk_reward':1.538,'usable_room_pct':1.0},
        'indicators': {'ema20':99.0,'ema50':98.0,'rsi14':60,'atr14':1.0,'momentum_24h_pct':1.0,'volume_ratio':0.5},
        'generated_at': '2026-08-24T21:00:00+00:00',
    }
    out = reliability._conditional_wait(atlas, dict(decision))
    cw = out['conditional_wait']

    assert out['score'] == 66
    assert out['signal_threshold'] == 68
    assert out['signal_qualified'] is False
    assert out['actionable_decision'] == 'WAIT'
    assert cw['status'] == 'ARMED_SHADOW_CONDITION', cw
    assert cw['requires_requalification'] is True
    assert cw['requalification_threshold'] == 68
    assert cw['production_unchanged'] is True
    assert cw['can_execute'] is False
    assert cw['risk_reward'] >= 1.0


def test_hype_hyperliquid_fallback_is_shadow_only():
    atlas = FakeAtlas()
    original_post = reliability._post_json
    try:
        def fake_post(url, payload, ua, timeout=18):
            if payload.get('type') == 'metaAndAssetCtxs':
                return [
                    {'universe':[{'name':'BTC'},{'name':'HYPE'}]},
                    [
                        {'markPx':'79000','oraclePx':'79005','openInterest':'100','funding':'0.00001','dayNtlVlm':'1000000'},
                        {'markPx':'44.5','oraclePx':'44.55','openInterest':'500000','funding':'0.00002','dayNtlVlm':'25000000'},
                    ],
                ]
            if payload.get('type') == 'l2Book':
                return {'levels':[[{'px':'44.4','sz':'1000'}],[{'px':'44.6','sz':'900'}]]}
            raise AssertionError(payload)
        reliability._post_json = fake_post
        snap = reliability._hyperliquid_hype_capture(atlas)
    finally:
        reliability._post_json = original_post

    assert snap['symbol'] == 'HYPEUSDT'
    assert math.isclose(snap['mark_price'], 44.5)
    assert snap['futures_provider'] == 'HYPERLIQUID_PERP_PUBLIC'
    assert snap['futures_evidence_validated'] is False
    assert snap['flow_proxy'] == 'NEUTRAL_NO_EQUIVALENT_TAKER_RATIO'
    assert snap['live_execution'] is False


if __name__ == '__main__':
    test_integrity_quality_separates_maturity_and_coverage()
    test_conditional_wait_keeps_production_gate_unchanged()
    test_hype_hyperliquid_fallback_is_shadow_only()
    print('production reliability tests: ok')
