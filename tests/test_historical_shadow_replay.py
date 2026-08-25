from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import historical_shadow_replay as hsr


def _row(direction='LONG', score=65, reason='SCORE_BELOW_SIGNAL_THRESHOLD', ret24=1.2):
    return {
        'candidate_direction': direction,
        'score': score,
        'threshold': 68,
        'reason': reason,
        'score_attribution': {'obstacle_reason': 'VERY_CLOSE'},
        'horizons': {
            '1h': {'directional_return_pct': 0.2 if direction in ('LONG','SHORT') else None, 'change_pct': 0.2},
            '3h': {'directional_return_pct': 0.4 if direction in ('LONG','SHORT') else None, 'change_pct': 0.4},
            '6h': {'directional_return_pct': 0.7 if direction in ('LONG','SHORT') else None, 'change_pct': 0.7},
            '12h': {'directional_return_pct': 0.9 if direction in ('LONG','SHORT') else None, 'change_pct': 0.9},
            '24h': {'directional_return_pct': ret24 if direction in ('LONG','SHORT') else None, 'change_pct': ret24},
        },
    }


def test_replay_counts_directional_and_target_progress():
    payload = {'records': [_row(), _row(score=70, ret24=-0.5), _row(direction='NONE', score=None, ret24=2.0)]}
    r = hsr.build_report(payload, target_cases=2)
    assert r['schema'] == 'ATLAS_HISTORICAL_SHADOW_REPLAY_V2_HORIZON_FIT'
    assert r['progress']['directional_shadow_records'] == 2
    assert r['progress']['directional_12h_matured'] == 2
    assert r['progress']['directional_24h_matured'] == 2
    assert r['progress']['target_reached_12h'] is True
    assert r['progress']['target_reached_24h'] is True
    assert r['progress']['target_reached_any_horizon'] is True
    assert r['horizon_fit']['target_by_horizon']['12h']['target_reached'] is True
    assert r['horizon_fit']['recommended_research_horizon'] == '12-24H'
    assert r['production_threshold_changed'] is False
    assert r['production_threshold'] == 68


def test_score_bands_and_states_are_separated_across_horizons():
    payload = {'records': [_row(score=59), _row(score=64), _row(score=70), _row(score=78)]}
    r = hsr.build_report(payload)
    assert r['by_score_band_by_horizon']['LT_60']['records'] == 1
    assert r['by_score_band_by_horizon']['60_67']['records'] == 1
    assert r['by_score_band_by_horizon']['68_74']['records'] == 1
    assert r['by_score_band_by_horizon']['75_PLUS']['records'] == 1
    assert r['by_score_band_by_horizon']['60_67']['horizons']['12h']['n'] == 1
    assert r['by_score_band_24h']['60_67']['at_24h']['n'] == 1
    assert r['by_opportunity_state_by_horizon']['WATCH']['records'] == 2
    assert r['by_opportunity_state_by_horizon']['QUALIFIED_BUT_BLOCKED']['records'] == 2


def test_no_setup_is_not_counted_as_directional_success():
    payload = {'records': [_row(direction='NONE', score=None, ret24=5.0)]}
    r = hsr.build_report(payload)
    assert r['progress']['directional_24h_matured'] == 0
    assert r['directional_forward_performance']['24h']['n'] == 0
    assert r['no_setup_market_move_context']['24h']['n'] == 1


if __name__ == '__main__':
    test_replay_counts_directional_and_target_progress()
    test_score_bands_and_states_are_separated_across_horizons()
    test_no_setup_is_not_counted_as_directional_success()
    print('historical shadow replay tests: ok')
