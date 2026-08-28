#!/usr/bin/env python3
import accepted_shadow_paired_revalidation as r
import counterfactual_episode_evaluation as p


def main():
    assert r.base.THRESHOLD == 68.0
    assert r.v6_baseline({'corrected_score':68}) is True
    assert r.v6_baseline({'corrected_score':67}) is False
    x = {'symbol':'BTCUSDT','direction':'LONG','captured_at':r.base.parse_time('2026-08-01T00:00:00+00:00')}
    assert p.episode_id(x).startswith('BTCUSDT|LONG|')
    print('accepted shadow paired revalidation tests: ok')

if __name__ == '__main__':
    main()
