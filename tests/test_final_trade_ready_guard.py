import os
import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import final_trade_ready_guard as guard
import paper_portfolio_10k_final as paper_final


def base_row(**extra):
    row = {
        'ok': True,
        'symbol': 'BTCUSDT',
        'candidate_direction': 'SHORT',
        'product_direction': 'SHORT',
        'entry_confirmation_direction': 'SHORT',
        'direction_alignment': 'ALIGNED',
        'production_signal_qualified': True,
        'actionable_decision': 'SHORT',
        'execution_ready': True,
        'data_degraded': False,
        'setup_quality_gate': {'status': 'PASS'},
        'htf_core_geometry': {'ready': True, 'reason': 'HTF_DIRECTION_AND_GEOMETRY_ALIGNED'},
        'trade_plan': {
            'direction': 'SHORT', 'entry': 100.0, 'stop_loss': 102.0, 'tp1': 98.0, 'tp2': 96.0,
            'rr_tp2': 2.0, 'analysis_ready': True, 'can_execute': True,
            'core_plan': {'analysis_ready': True, 'can_execute': True, 'action': 'SELL', 'status': 'ACTIONABLE'},
        },
        'primary_analysis': {'decision': 'SHORT', 'analysis_ready': True},
        'timeframe_matrix': {'core_4_12h': {'decision': 'SHORT', 'analysis_ready': True}},
        'best_available_action': {'action': 'SHORT', 'status': 'ACTIONABLE', 'can_execute': True},
        'analyst_output': {
            'decision': 'SHORT', 'analysis_ready': True, 'entry': 100.0, 'stop_loss': 102.0,
            'take_profit': 96.0, 'tp1': 98.0, 'risk_reward': 2.0,
            'candidate_plan': {
                'direction': 'SHORT', 'entry': 100.0, 'stop_loss': 102.0,
                'take_profit': 96.0, 'tp1': 98.0, 'risk_reward': 2.0,
                'geometry_provenance': {'geometry_version': 'TEST'},
            },
            'geometry_readiness': {'ready': True, 'reason': 'HTF_DIRECTION_AND_GEOMETRY_ALIGNED'},
        },
    }
    row.update(extra)
    return row


def test_aligned_actionable_is_certified_trade_ready():
    r = guard.apply(base_row())
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['status'] == 'TRADE_READY'
    assert r['final_trade_gate']['direction'] == 'SHORT'
    assert paper_final.strict_trade_ready(r) is True


def test_production_stale_wait_still_fails_closed_by_default():
    old=os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
    try:
        r=guard.apply(base_row(actionable_decision='WAIT'))
        assert r['trade_ready'] is False
        assert 'PRE_FINAL_DECISION_NOT_ACTIONABLE' in r['final_trade_gate']['blockers']
        assert r['final_trade_gate']['experimental_final_evidence_promotion'] is False
    finally:
        if old is not None: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_isolated_evidence_can_bypass_only_stale_pre_final_wait_and_restore_geometry():
    old=os.environ.get(guard.EXPERIMENTAL_PROMOTION_ENV)
    os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]='1'
    try:
        d=base_row(actionable_decision='WAIT')
        d['analyst_output']=dict(d['analyst_output'])
        d['analyst_output'].update({'decision':'WAIT','analysis_ready':False,'entry':None,'stop_loss':None,'take_profit':None,'tp1':None,'risk_reward':None})
        r=guard.apply(d)
        assert r['trade_ready'] is True
        assert r['final_trade_gate']['direction'] == 'SHORT'
        assert r['final_trade_gate']['stale_pre_final_wait_bypassed'] is True
        assert r['final_trade_gate']['experimental_candidate_geometry_restored'] is True
        assert r['final_trade_gate']['score_changed'] is False
        assert r['final_trade_gate']['threshold_changed'] is False
        a=r['analyst_output']
        assert a['decision']=='SHORT' and a['analysis_ready'] is True
        assert a['entry']==100.0 and a['stop_loss']==102.0 and a['take_profit']==96.0
        assert a['tp1']==98.0 and a['risk_reward']==2.0
    finally:
        if old is None: os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
        else: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_experimental_bypass_fails_closed_when_candidate_geometry_is_missing():
    old=os.environ.get(guard.EXPERIMENTAL_PROMOTION_ENV)
    os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]='1'
    try:
        d=base_row(actionable_decision='WAIT')
        d['analyst_output']=dict(d['analyst_output'])
        d['analyst_output']['candidate_plan']={'direction':'SHORT','entry':100.0,'stop_loss':102.0,'take_profit':None}
        r=guard.apply(d)
        assert r['trade_ready'] is False
        assert 'EXPERIMENTAL_CANDIDATE_PLAN_INCOMPLETE' in r['final_trade_gate']['blockers']
    finally:
        if old is None: os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
        else: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_experimental_bypass_does_not_override_real_safety_blocker():
    old=os.environ.get(guard.EXPERIMENTAL_PROMOTION_ENV)
    os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]='1'
    try:
        r=guard.apply(base_row(actionable_decision='WAIT', setup_quality_gate={'status':'BLOCK'}))
        assert r['trade_ready'] is False
        assert 'SETUP_QUALITY_GATE_BLOCKED' in r['final_trade_gate']['blockers']
    finally:
        if old is None: os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
        else: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_unresolved_product_direction_fails_closed_and_collapses_nested_plan():
    r = guard.apply(base_row(product_direction=None, direction_alignment='4H_12H_NOT_ALIGNED'))
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'HTF_PRODUCT_DIRECTION_UNRESOLVED' in r['final_trade_gate']['blockers']
    assert r['trade_plan']['analysis_ready'] is False
    assert r['trade_plan']['can_execute'] is False
    assert r['trade_plan']['core_plan']['analysis_ready'] is False
    assert r['trade_plan']['core_plan']['can_execute'] is False
    assert r['analyst_output']['decision'] == 'WAIT'
    assert r['analyst_output']['entry'] is None
    assert paper_final.strict_trade_ready(r) is False


def test_candidate_direction_cannot_override_htf_product_direction():
    r = guard.apply(base_row(candidate_direction='SHORT', product_direction='LONG', entry_confirmation_direction='LONG', direction_alignment='ALIGNED'))
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'SCORE_DIRECTION_NOT_HTF_DIRECTION' in r['final_trade_gate']['blockers']


def test_geometry_not_ready_blocks_even_with_high_legacy_readiness():
    r = guard.apply(base_row(htf_core_geometry={'ready': False, 'reason': 'INSUFFICIENT_HTF_ROOM_TO_TARGET'}))
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'INSUFFICIENT_HTF_ROOM_TO_TARGET' in r['final_trade_gate']['blockers']


def test_legacy_execution_ready_is_never_enough_for_paper_portfolio():
    d = base_row()
    d['trade_ready'] = False
    d['final_trade_gate'] = {'status': 'WAIT', 'trade_ready': False, 'direction': None}
    assert d['execution_ready'] is True and d['trade_plan']['can_execute'] is True
    assert paper_final.strict_trade_ready(d) is False


def test_missing_final_gate_is_rejected_by_paper_portfolio():
    d = base_row()
    d.pop('final_trade_gate', None)
    d.pop('trade_ready', None)
    assert paper_final.strict_trade_ready(d) is False


def test_quality_quarantine_and_degraded_data_fail_closed():
    q = guard.apply(base_row(setup_quality_gate={'status': 'BLOCK'}))
    assert q['trade_ready'] is False and 'SETUP_QUALITY_GATE_BLOCKED' in q['final_trade_gate']['blockers']
    d = guard.apply(base_row(data_degraded=True))
    assert d['trade_ready'] is False and 'DATA_DEGRADED' in d['final_trade_gate']['blockers']


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    for t in tests:
        t()
    print(f'final trade ready guard tests: {len(tests)} passed')
