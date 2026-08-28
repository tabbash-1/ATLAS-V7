#!/usr/bin/env python3
from long_v7_train_fitted_ranker import fit, quality, evaluate


def row(symbol, score, vol, rs, trend, votes, obstacle, futures, ret):
    return {
        'symbol': symbol,
        'captured_at': f'2026-08-20T0{len(symbol)%9}:00:00+00:00',
        'direction': 'LONG',
        'corrected_score': score,
        'volume_bonus': vol,
        'rs_adjustment': rs,
        'trend_base': trend,
        'direction_votes': votes,
        'obstacle_adjustment': obstacle,
        'futures_adjustment': futures,
        'return_12h_pct': ret,
    }


def test_fit_uses_component_relationships():
    train = [
        row('A', 75, -6, 5, 50, 4, -4, 4, -2.0),
        row('B', 72, 0, 2, 50, 4, -4, 2, -1.0),
        row('C', 65, 5, -2, 34, 3, 0, 0, 2.0),
        row('D', 62, 5, -5, 34, 3, 3, -2, 3.0),
    ]
    p = fit(train)
    assert p['volume_bonus']['weight'] > 0
    assert quality(train[-1], p) > quality(train[0], p)


def test_equal_mature_coverage():
    pool = [
        row('A', 75, -6, 5, 50, 4, -4, 4, -2.0),
        row('B', 72, 0, 2, 50, 4, -4, 2, -1.0),
        row('C', 65, 5, -2, 34, 3, 0, 0, 2.0),
        row('D', 62, 5, -5, 34, 3, 3, -2, 3.0),
    ]
    p = fit(pool)
    out = evaluate(pool, p)
    assert out['equal_mature_coverage_k'] == 2
    assert out['baseline_v6']['n'] == 2
    assert out['candidate_v7']['n'] == 2


def test_research_guardrails_in_source():
    import long_v7_train_fitted_ranker as m
    src = open(m.__file__, encoding='utf-8').read()
    assert "'fit_scope': 'TRAIN_ONLY'" in src
    assert "'no_threshold_search': True" in src
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_fit_uses_component_relationships()
    test_equal_mature_coverage()
    test_research_guardrails_in_source()
    print('long v7 train-fitted ranker tests: ok')
