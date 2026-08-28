#!/usr/bin/env python3
from long_v7_anti_chase_candidate import evaluate


def row(symbol, score, mom, ret):
    return {
        'symbol': symbol,
        'captured_at': f'2026-08-20T{len(symbol)%20:02d}:00:00+00:00',
        'direction': 'LONG',
        'corrected_score': score,
        'momentum_24h_pct': mom,
        'return_12h_pct': ret,
    }


def test_equal_coverage_anti_chase_ranking():
    rows = [
        row('A', 75, 5.0, -2.0),
        row('BB', 72, 4.0, -1.0),
        row('CCC', 65, 0.5, 2.0),
        row('DDDD', 64, 1.0, 3.0),
    ]
    out = evaluate(rows)
    assert out['equal_mature_coverage_k'] == 2
    assert out['baseline_v6']['n'] == 2
    assert out['candidate_anti_chase']['n'] == 2
    assert out['comparison']['mean_delta_pct'] > 0


def test_guardrails():
    import long_v7_anti_chase_candidate as m
    src = open(m.__file__, encoding='utf-8').read()
    assert "'production_threshold_changed': False" in src
    assert "'production_scoring_changed': False" in src
    assert "'can_override_production': False" in src
    assert "'live_execution': False" in src


if __name__ == '__main__':
    test_equal_coverage_anti_chase_ranking()
    test_guardrails()
    print('long v7 anti-chase candidate tests: ok')
