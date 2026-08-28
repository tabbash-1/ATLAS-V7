#!/usr/bin/env python3
from long_v7_raw_representation_audit import enrich_row


def test_raw_feature_transforms():
    import qualified_false_confidence_audit as base
    old = base.replay_observation
    try:
        base.replay_observation = lambda ts, symbol, d: {
            'excluded': None,
            'direction': 'LONG',
            'entry': 110.0,
            'relative_volume_replayed': 1.25,
        }
        d = {'indicators': {
            'ema20': 100.0,
            'ema50': 95.0,
            'rsi14': 60.0,
            'atr14': 5.0,
            'momentum_24h_pct': 2.0,
            'volume_ratio': 0.5,
        }}
        r = enrich_row(None, 'X', d)
        assert round(r['price_vs_ema20_pct'], 6) == 10.0
        assert round(r['ema20_vs_ema50_pct'], 6) == round((100/95-1)*100, 6)
        assert r['price_extension_atr'] == 2.0
        assert r['atr_pct'] == 5/110*100
        assert r['paced_relative_volume'] == 1.25
    finally:
        base.replay_observation = old


def test_guardrails_in_source():
    import long_v7_raw_representation_audit as m
    src = open(m.__file__, encoding='utf-8').read()
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_raw_feature_transforms()
    test_guardrails_in_source()
    print('long v7 raw representation audit tests: ok')
