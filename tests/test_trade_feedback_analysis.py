from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import trade_feedback_analysis as t


def rec(symbol='BTCUSDT', direction='LONG', state='TP2 HIT', r=2.0, pnl=100, mode='BREAKOUT', evidence=None):
    return {
        'symbol': symbol,
        'direction': direction,
        'state': state,
        'r_multiple': r,
        'pnl_usdt': pnl,
        'entry_mode': mode,
        'evidence': evidence or [
            {'name': 'relative_volume', 'value': 0.5},
            {'name': 'futures', 'value': -0.3},
        ],
    }


def test_feedback_report_is_research_only():
    r = t.build_report({'records': [rec(), rec(state='STOPPED', r=-1, pnl=-50)]})
    assert r['closed_records'] == 2
    assert r['research_only'] is True
    assert r['auto_promotion_enabled'] is False
    assert r['production_threshold_changed'] is False
    assert r['production_score_adjustment'] == 0
    assert r['research_tier'] == 'HYPOTHESIS'


def test_non_closed_observations_do_not_count():
    r = t.build_report({'records': [rec(state='ACTIVE'), rec(state='PRE-ENTRY'), rec()]})
    assert r['saved_records'] == 3
    assert r['closed_records'] == 1
    assert r['overall']['n'] == 1


def test_twenty_closed_trades_can_reach_serious_research_tier_only():
    rows = [rec(r=1 if i % 2 == 0 else -1, pnl=10 if i % 2 == 0 else -10) for i in range(20)]
    r = t.build_report({'records': rows})
    assert r['research_tier'] == 'SERIOUS_CANDIDATE'
    assert r['auto_promotion_enabled'] is False


def test_evidence_split_requires_five_each_side():
    rows = []
    for i in range(5):
        rows.append(rec(r=1, evidence=[{'name': 'futures', 'value': 0.5}]))
        rows.append(rec(r=-1, evidence=[{'name': 'futures', 'value': -0.5}]))
    r = t.build_report({'records': rows})
    e = r['evidence_attribution']['futures']
    assert e['positive']['n'] == 5
    assert e['negative']['n'] == 5
    assert e['enough_for_split_review'] is True
    assert e['delta_mean_r'] == 2.0


if __name__ == '__main__':
    test_feedback_report_is_research_only()
    test_non_closed_observations_do_not_count()
    test_twenty_closed_trades_can_reach_serious_research_tier_only()
    test_evidence_split_requires_five_each_side()
    print('trade feedback analysis tests: ok')
