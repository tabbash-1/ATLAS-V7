#!/usr/bin/env python3
from long_v7_regime_map_audit import bucket_momentum, bucket_rsi, bucket_extension, bucket_rv, stable_compare


def test_pre_registered_bins():
    assert bucket_momentum(-0.1) == '<=0'
    assert bucket_momentum(0.5) == '0_1'
    assert bucket_momentum(1.5) == '1_2'
    assert bucket_momentum(3.0) == '2_4'
    assert bucket_momentum(5.0) == '>4'
    assert bucket_rsi(54.9) == '<55'
    assert bucket_rsi(60) == '55_62'
    assert bucket_rsi(65) == '62_68'
    assert bucket_rsi(70) == '68_72'
    assert bucket_rsi(75) == '>=72'
    assert bucket_extension(-0.1) == '<0'
    assert bucket_extension(0.3) == '0_0.5'
    assert bucket_extension(0.8) == '0.5_1'
    assert bucket_extension(1.2) == '1_1.5'
    assert bucket_extension(2.0) == '>=1.5'
    assert bucket_rv(0.5) == '<0.7'
    assert bucket_rv(0.8) == '0.7_1'
    assert bucket_rv(1.2) == '1_1.5'
    assert bucket_rv(2.0) == '1.5_2.5'
    assert bucket_rv(3.0) == '>=2.5'


def test_stability_requires_both_lanes():
    tr = {'A': {'n': 2, 'mean_pct': 1.0}, 'B': {'n': 2, 'mean_pct': -1.0}}
    ho = {'A': {'n': 2, 'mean_pct': 0.5}, 'B': {'n': 2, 'mean_pct': -0.2}}
    hp, hm = stable_compare(tr, ho)
    assert [x['bucket'] for x in hp] == ['A']
    assert [x['bucket'] for x in hm] == ['B']


def test_guardrails():
    import long_v7_regime_map_audit as m
    src = open(m.__file__, encoding='utf-8').read()
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_pre_registered_bins()
    test_stability_requires_both_lanes()
    test_guardrails()
    print('long v7 regime map audit tests: ok')
