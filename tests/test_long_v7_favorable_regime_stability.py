#!/usr/bin/env python3
from long_v7_favorable_regime_stability import is_regime


def test_regime_boundaries_are_frozen():
    assert is_regime({'momentum_24h_pct': 1.5, 'price_extension_atr': 0.75})
    assert not is_regime({'momentum_24h_pct': 1.0, 'price_extension_atr': 0.75})
    assert not is_regime({'momentum_24h_pct': 2.1, 'price_extension_atr': 0.75})
    assert not is_regime({'momentum_24h_pct': 1.5, 'price_extension_atr': 0.49})
    assert not is_regime({'momentum_24h_pct': 1.5, 'price_extension_atr': 1.0})


def test_guardrails():
    import long_v7_favorable_regime_stability as m
    src = open(m.__file__, encoding='utf-8').read()
    assert 'POST_SELECTION_STRESS_TEST_NOT_CLEAN_HOLDOUT' in src
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_regime_boundaries_are_frozen()
    test_guardrails()
    print('long v7 favorable regime stability tests: ok')
