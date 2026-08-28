#!/usr/bin/env python3
from long_v7_volume_quality_candidate import _k_from_v6, _rank_candidate, _rank_v6, lane


def row(symbol, ts, score, volume_bonus, ret):
    return {
        'symbol': symbol,
        'captured_at': ts,
        'direction': 'LONG',
        'corrected_score': score,
        'volume_bonus': volume_bonus,
        'return_12h_pct': ret,
    }


def test_equal_coverage_and_rankers():
    # Spaced by >12h per symbol so all rows remain independent anchors.
    rows = [
        row('BTCUSDT', '2026-08-20T00:00:00+00:00', 75, -6, -2.0),
        row('ETHUSDT', '2026-08-20T00:00:00+00:00', 72, 2, -1.0),
        row('SOLUSDT', '2026-08-20T00:00:00+00:00', 66, 5, 3.0),
        row('XRPUSDT', '2026-08-20T00:00:00+00:00', 64, 5, 2.0),
    ]
    assert _k_from_v6(rows) == 2
    assert [x['symbol'] for x in _rank_v6(rows)[:2]] == ['BTCUSDT', 'ETHUSDT']
    assert [x['symbol'] for x in _rank_candidate(rows)[:2]] == ['SOLUSDT', 'XRPUSDT']

    out = lane(rows)
    assert out['equal_coverage_k'] == 2
    assert out['baseline_v6_topk']['n'] == 2
    assert out['candidate_volume_topk']['n'] == 2
    assert out['comparison']['mean_delta_pct'] > 0


def test_no_production_mutation_contract():
    import long_v7_volume_quality_candidate as m
    src = open(m.__file__, encoding='utf-8').read()
    assert 'production_change_recommended' in src
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_equal_coverage_and_rankers()
    test_no_production_mutation_contract()
    print('long v7 volume quality candidate tests: ok')
