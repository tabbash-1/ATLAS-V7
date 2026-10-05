import os
import pathlib
import sys
import types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import final_trade_ready_guard as guard
import paper_portfolio_10k_final as paper_final

# Most fixtures exercise downstream SHORT mechanics explicitly. Production now
# defaults to the same evidence-gated path; the environment variable is retained
# as an emergency kill switch.
os.environ[guard.SHORT_PRODUCTION_ENV] = '1'


def base_row(**extra):
    row = {
        'ok': True,
        'symbol': 'BTCUSDT',
        'candidate_direction': 'SHORT',
        'product_direction': 'SHORT',
        'entry_confirmation_direction': 'SHORT',
        'direction_alignment': 'ALIGNED',
        'htf_thesis': {
            'status': 'PASS',
            'reason': 'HTF_ALIGNED_CURRENT_PHASE_ACCEPTABLE',
            'product_direction': 'SHORT',
            'entry_confirmation_direction': 'SHORT',
            'direction_alignment': 'ALIGNED',
        },
        'market_direction_gate': {'pass': True, 'reason': 'BTC_IS_MARKET_ANCHOR'},
        'production_signal_qualified': True,
        'actionable_decision': 'SHORT',
        'execution_ready': True,
        'data_degraded': False,
        # Optional reporting evidence. It does not decide the analyst's view.
        'execution_cost': {'validated': True, 'fee_bps': 0.0, 'spread_bps': 0.0, 'slippage_bps': 0.0},
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


def long_row(entry_mode):
    row = base_row(
        candidate_direction='LONG', product_direction='LONG',
        entry_confirmation_direction='LONG', actionable_decision='LONG',
    )
    plan = dict(row['trade_plan'])
    plan.update({'direction':'LONG','entry':100.0,'stop_loss':98.0,'tp1':102.0,'tp2':104.0,'rr_tp2':2.0,'entry_mode':entry_mode})
    plan['core_plan'] = dict(plan['core_plan'], direction='LONG', entry_mode=entry_mode)
    row['trade_plan'] = plan
    row['primary_analysis'] = {'decision':'LONG','analysis_ready':True}
    row['timeframe_matrix'] = {'core_4_12h':{'decision':'LONG','analysis_ready':True}}
    row['best_available_action'] = {'action':'LONG','status':'ACTIONABLE','can_execute':True}
    analyst = dict(row['analyst_output'])
    analyst.update({'decision':'LONG','entry':100.0,'stop_loss':98.0,'take_profit':104.0,'tp1':102.0,'risk_reward':2.0})
    analyst['candidate_plan'] = {'direction':'LONG','entry':100.0,'stop_loss':98.0,'take_profit':104.0,'tp1':102.0,'risk_reward':2.0,'geometry_provenance':{'geometry_version':'TEST'}}
    row['analyst_output'] = analyst
    return row


def test_short_is_evidence_gated_by_default_without_explicit_env():
    old = os.environ.pop(guard.SHORT_PRODUCTION_ENV, None)
    try:
        r = guard.apply(base_row())
        assert r['trade_ready'] is True
        assert r['final_trade_gate']['direction'] == 'SHORT'
        assert 'SHORT_EDGE_NOT_PROVEN_PRODUCTION_QUARANTINE' not in r['final_trade_gate']['blockers']
    finally:
        if old is not None:
            os.environ[guard.SHORT_PRODUCTION_ENV] = old


def test_short_emergency_kill_switch_still_fails_closed():
    old = os.environ.get(guard.SHORT_PRODUCTION_ENV)
    os.environ[guard.SHORT_PRODUCTION_ENV] = '0'
    try:
        r = guard.apply(base_row())
        assert r['trade_ready'] is False
        assert 'SHORT_EDGE_NOT_PROVEN_PRODUCTION_QUARANTINE' in r['final_trade_gate']['blockers']
    finally:
        if old is None:
            os.environ.pop(guard.SHORT_PRODUCTION_ENV, None)
        else:
            os.environ[guard.SHORT_PRODUCTION_ENV] = old


def test_aligned_actionable_is_certified_trade_ready():
    r = guard.apply(base_row())
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['status'] == 'TRADE_READY'
    assert r['final_trade_gate']['direction'] == 'SHORT'
    assert paper_final.strict_trade_ready(r) is True


def test_unconfirmed_breakout_continuation_fails_closed():
    d = base_row(
        playbook='BREAKOUT_CONTINUATION_SHORT',
        structural_geometry={'breakout': {'confirmed': False}},
    )
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'BREAKOUT_STRUCTURE_NOT_CONFIRMED' in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['structure_confirmation']['requires_confirmation'] is True
    assert r['final_trade_gate']['structure_confirmation']['confirmed'] is False
    assert paper_final.strict_trade_ready(r) is False


def test_confirmed_breakout_still_can_pass_final_gate():
    d = base_row(
        playbook='BREAKOUT_CONFIRMED_SHORT',
        structural_geometry={'breakout': {'confirmed': True}},
    )
    r = guard.apply(d)
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['status'] == 'TRADE_READY'
    assert r['final_trade_gate']['structure_confirmation']['requires_confirmation'] is True
    assert r['final_trade_gate']['structure_confirmation']['confirmed'] is True
    assert r['final_trade_gate']['score_changed'] is False
    assert r['final_trade_gate']['threshold_changed'] is False


def test_breakout_without_canonical_confirmation_evidence_fails_closed():
    d = base_row(playbook='BREAKOUT_CONTINUATION_SHORT')
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert 'BREAKOUT_CONFIRMATION_EVIDENCE_MISSING' in r['final_trade_gate']['blockers']


def _confirmed_short_pullback_thesis():
    return {
        'status': 'PASS',
        'reason': 'HTF_ALIGNED_CURRENT_PHASE_ACCEPTABLE',
        'product_direction': 'SHORT',
        'entry_confirmation_direction': 'SHORT',
        'direction_alignment': 'ALIGNED',
        'frames': {
            '1h': {
                'bias': 'SHORT',
                'impulse': 'BEARISH',
                'candle': {'direction': 'BEARISH', 'pattern': 'BEARISH_ENGULFING'},
            }
        }
    }


def test_non_breakout_pullback_requires_fresh_bearish_resumption():
    d = base_row(playbook='TREND_PULLBACK_SHORT', htf_thesis=_confirmed_short_pullback_thesis())
    r = guard.apply(d)
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['structure_confirmation']['requires_confirmation'] is False
    assert r['final_trade_gate']['trader_brain']['short_pullback_resumption_confirmed'] is True


def test_short_pullback_without_resumption_fails_closed():
    d = base_row(
        playbook='TREND_PULLBACK_SHORT',
        htf_thesis={'frames': {'1h': {
            'bias': 'SHORT',
            'impulse': 'BULLISH',
            'candle': {'direction': 'BULLISH', 'pattern': 'NORMAL'},
        }}},
    )
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert 'TRADER_WAIT_SHORT_PULLBACK_RESUMPTION' in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['trader_brain']['short_pullback_resumption_confirmed'] is False


def test_short_pullback_missing_1h_evidence_fails_closed():
    d = base_row(playbook='TREND_PULLBACK_SHORT')
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert 'TRADER_WAIT_SHORT_PULLBACK_RESUMPTION' in r['final_trade_gate']['blockers']


def test_stale_pre_final_wait_fails_closed_when_kill_switch_disables_promotion():
    old=os.environ.get(guard.EXPERIMENTAL_PROMOTION_ENV)
    os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]='0'
    try:
        r=guard.apply(base_row(actionable_decision='WAIT'))
        assert r['trade_ready'] is False
        assert 'PRE_FINAL_WAIT_PROMOTION_DISABLED' in r['final_trade_gate']['blockers']
        assert r['final_trade_gate']['legacy_pre_final_action_is_authority'] is False
        assert r['final_trade_gate']['score_is_authority'] is False
    finally:
        if old is None: os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
        else: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_evidence_complete_stale_wait_is_promoted_by_default():
    old=os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
    try:
        d=base_row(actionable_decision='WAIT')
        d['analyst_output']=dict(d['analyst_output'])
        d['analyst_output'].update({'decision':'WAIT','analysis_ready':False,'entry':None,'stop_loss':None,'take_profit':None,'tp1':None,'risk_reward':None})
        r=guard.apply(d)
        assert r['trade_ready'] is True
        assert r['final_trade_gate']['direction'] == 'SHORT'
        assert r['final_trade_gate']['stale_pre_final_wait_bypassed'] is True
        assert r['final_trade_gate']['score_changed'] is False
        assert r['final_trade_gate']['threshold_changed'] is False
        assert r['actionable_decision'] == 'SHORT'
        assert r['analysis_ready'] is True and r['can_execute'] is True
        assert r['trade_plan']['status'] == 'TRADE_READY'
        assert r['trade_plan']['action'] == 'SHORT'
    finally:
        if old is not None: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old


def test_night_correction_captures_only_evidence_complete_shorts():
    """Regression for the 2026-10-03 correction: capture DOGE/ADA, not weak ZEC."""
    old_short=os.environ.pop(guard.SHORT_PRODUCTION_ENV, None)
    old_promotion=os.environ.pop(guard.EXPERIMENTAL_PROMOTION_ENV, None)
    try:
        doge=guard.apply(base_row(
            symbol='DOGEUSDT', score=70,
            playbook='TREND_PULLBACK_SHORT',
            htf_thesis=_confirmed_short_pullback_thesis(),
        ))
        assert doge['trade_ready'] is True
        assert doge['canonical_decision']['decision'] == 'SHORT'
        assert doge['final_trade_gate']['threshold_changed'] is False

        ada=base_row(
            symbol='ADAUSDT', score=75, actionable_decision='WAIT',
            playbook='TREND_PULLBACK_SHORT',
            htf_thesis=_confirmed_short_pullback_thesis(),
        )
        ada['analyst_output']=dict(ada['analyst_output'])
        ada['analyst_output'].update({'decision':'WAIT','analysis_ready':False,'entry':None,'stop_loss':None,'take_profit':None,'tp1':None,'risk_reward':None})
        ada=guard.apply(ada)
        assert ada['trade_ready'] is True
        assert ada['canonical_decision']['decision'] == 'SHORT'
        assert ada['final_trade_gate']['stale_pre_final_wait_bypassed'] is True
        assert ada['actionable_decision'] == 'SHORT'
        assert ada['trade_plan']['status'] == 'TRADE_READY'

        zec=guard.apply(base_row(
            symbol='ZECUSDT', score=79, actionable_decision='WAIT',
            htf_core_geometry={'ready':False,'reason':'RR_BELOW_TWO_TO_ONE'},
            playbook='TREND_PULLBACK_SHORT',
            htf_thesis=_confirmed_short_pullback_thesis(),
        ))
        assert zec['trade_ready'] is False
        assert zec['canonical_decision']['decision'] == 'WAIT'
        assert 'RR_BELOW_TWO_TO_ONE' in zec['final_trade_gate']['blockers']
    finally:
        if old_short is not None: os.environ[guard.SHORT_PRODUCTION_ENV]=old_short
        if old_promotion is not None: os.environ[guard.EXPERIMENTAL_PROMOTION_ENV]=old_promotion


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
    d = base_row(product_direction=None, direction_alignment='4H_12H_NOT_ALIGNED')
    d['htf_thesis'] = {
        'status':'WAIT',
        'reason':'4H_12H_NOT_ALIGNED',
        'product_direction':None,
        'direction':None,
        'entry_confirmation_direction':'SHORT',
        'direction_alignment':'4H_12H_NOT_ALIGNED',
    }
    r = guard.apply(d)
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


def test_legacy_score_direction_is_evidence_not_authority():
    r = guard.apply(base_row(candidate_direction='LONG', product_direction='SHORT', entry_confirmation_direction='SHORT', direction_alignment='ALIGNED'))
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['direction'] == 'SHORT'
    assert r['final_trade_gate']['score_is_authority'] is False


def test_entry_confirmation_opposition_is_not_mislabeled_as_htf_disagreement():
    r = guard.apply(base_row(
        product_direction='LONG',
        entry_confirmation_direction='SHORT',
        direction_alignment='OPPOSED',
    ))
    blockers = r['final_trade_gate']['blockers']
    assert r['trade_ready'] is False
    assert 'ENTRY_CONFIRMATION_NOT_ALIGNED' in blockers
    assert 'HTF_4H_12H_NOT_ALIGNED' not in blockers


def test_trader_brain_requires_two_r_geometry():
    d=base_row()
    d['trade_plan']=dict(d['trade_plan']); d['trade_plan']['rr_tp2']=1.5
    r=guard.apply(d)
    assert r['trade_ready'] is False
    assert 'TRADER_RR_BELOW_2R' in r['final_trade_gate']['blockers']


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


def test_conditional_neutral_alignment_is_paper_eligible_when_trader_ready():
    d=base_row(direction_alignment='CONDITIONAL_ALIGNED_12H_NEUTRAL')
    d['trade_plan']['rr_tp2']=2.0
    r=guard.apply(d)
    assert r['trade_ready'] is True
    assert paper_final.strict_trade_ready(r) is True


def test_paper_rejects_sub_two_r_even_if_legacy_fields_look_ready():
    d=base_row()
    d['trade_plan']=dict(d['trade_plan']); d['trade_plan']['rr_tp2']=1.5
    r=guard.apply(d)
    assert r['trade_ready'] is False
    assert paper_final.strict_trade_ready(r) is False


def test_blowoff_now_entry_waits_for_pullback_retest():
    d=long_row('NOW')
    d['score_attribution']={'extension_guard_reason':'BLOWOFF_RSI_LONG','extension_guard_adjustment':-4}
    r=guard.apply(d)
    assert r['trade_ready'] is False
    tb=r['final_trade_gate']['trader_brain']
    assert tb['stage']=='WAIT_LOCATION'
    assert tb['location_state']=='OVEREXTENDED'
    assert tb['desired_entry_mode']=='PULLBACK_RETEST'
    assert 'TRADER_WAIT_PULLBACK_RETEST' in r['final_trade_gate']['blockers']
    assert 'TRADER_NO_CHASE' in r['final_trade_gate']['blockers']


def test_blowoff_pullback_entry_can_pass_if_other_evidence_is_ready():
    d=long_row('PULLBACK')
    d['score_attribution']={'extension_guard_reason':'BLOWOFF_RSI_LONG','extension_guard_adjustment':-4}
    r=guard.apply(d)
    assert r['trade_ready'] is False
    assert r['final_trade_gate']['trader_brain']['desired_entry_mode']=='PULLBACK'

def test_validated_execution_costs_must_leave_at_least_two_r():
    d=base_row()
    d['trade_plan']=dict(d['trade_plan']); d['trade_plan']['rr_tp2']=2.0
    d['execution_cost']={'validated':True,'fee_bps':5.0,'spread_bps':1.0,'slippage_bps':2.0}
    r=guard.apply(d)
    assert r['trade_ready'] is True
    assert 'NET_RR_AFTER_COSTS_BELOW_2R' not in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['net_rr_after_costs']['net_rr'] < 2.0
    assert r['final_trade_gate']['execution_costs_affect_analysis_decision'] is False

def test_validated_execution_costs_can_pass_when_net_rr_stays_above_two_r():
    d=base_row()
    d['trade_plan']=dict(d['trade_plan']); d['trade_plan'].update({'rr_tp2':2.5,'tp2':95.0})
    d['execution_cost']={'validated':True,'fee_bps':5.0,'spread_bps':1.0,'slippage_bps':2.0}
    r=guard.apply(d)
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['net_rr_after_costs']['validated'] is True
    assert r['final_trade_gate']['net_rr_after_costs']['net_rr'] >= 2.0

def test_missing_cost_evidence_fails_closed_without_inventing_costs():
    d=base_row(); d.pop('execution_cost')
    r=guard.apply(d)
    n=r['final_trade_gate']['net_rr_after_costs']
    assert n['validated'] is False
    assert n['reason']=='EXECUTION_COST_EVIDENCE_UNAVAILABLE'
    assert n['cost_snapshot_status']=='NOT_ATTACHED_TO_PRODUCTION_DECISION'
    assert n['configuration_required'] is None
    assert n['report_note'] == 'Execution cost evidence is unavailable; net R:R is not reported.'
    assert r['final_trade_gate']['net_rr_cost_evidence_required_for_claim'] is True
    assert r['final_trade_gate']['net_rr_cost_evidence_required_for_trade_ready'] is False
    assert r['final_trade_gate']['execution_costs_affect_analysis_decision'] is False
    assert 'EXECUTION_COST_EVIDENCE_UNAVAILABLE' not in r['final_trade_gate']['blockers']
    assert r['trade_ready'] is True
    assert paper_final.strict_trade_ready(r) is True

def test_long_analysis_does_not_wait_for_venue_cost_configuration():
    d=long_row('PULLBACK')
    d.pop('execution_cost')
    r=guard.apply(d)
    assert r['actionable_decision']=='LONG'
    assert r['final_trade_gate']['direction']=='LONG'
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['net_rr_after_costs']['validated'] is False
    assert 'EXECUTION_COST_EVIDENCE_UNAVAILABLE' not in r['final_trade_gate']['blockers']

def test_runtime_cost_snapshot_is_consumed_by_final_gate():
    d=base_row()
    d.pop('execution_cost')
    d['trade_plan']=dict(d['trade_plan']); d['trade_plan'].update({'rr_tp2':2.5,'tp2':95.0})
    d['profit_engine_shadow']={
        'execution': {
            'validated': True, 'fee_bps': 5.0, 'spread_bps': 1.0,
            'slippage_bps': 2.0, 'basis': 'LIVE_OKX_SWAP_L2_PLUS_CONFIGURED_TAKER_FEE',
            'version': 'EXECUTION_COST_MODEL_TEST',
        },
    }
    r=guard.apply(d)
    net=r['final_trade_gate']['net_rr_after_costs']
    assert net['validated'] is True
    assert net['cost_source_version']=='EXECUTION_COST_MODEL_TEST'
    assert net['cost_basis']=='LIVE_OKX_SWAP_L2_PLUS_CONFIGURED_TAKER_FEE'
    assert net['net_rr'] >= 2.0

def test_runtime_cost_blockers_are_visible_when_configuration_is_missing():
    d=base_row()
    d.pop('execution_cost')
    d['profit_engine_shadow']={
        'execution': {'validated': False, 'basis': 'LIVE_OKX_SWAP_L2_PLUS_CONFIGURED_TAKER_FEE'},
        'execution_cost_source_version': 'EXECUTION_COST_MODEL_TEST',
        'execution_cost_blockers': ['EXECUTION_VENUE_NOT_CONFIGURED','TAKER_FEE_NOT_CONFIGURED'],
    }
    r=guard.apply(d)
    net=r['final_trade_gate']['net_rr_after_costs']
    assert net['validated'] is False
    assert net['reason']=='EXECUTION_COST_EVIDENCE_UNAVAILABLE'
    assert net['cost_source_version']=='EXECUTION_COST_MODEL_TEST'
    assert net['cost_blockers']==['EXECUTION_VENUE_NOT_CONFIGURED','TAKER_FEE_NOT_CONFIGURED']

def test_invalid_cost_evidence_fails_closed():
    d=base_row(execution_cost={'validated':True,'fee_bps':-1.0,'spread_bps':1.0,'slippage_bps':1.0})
    r=guard.apply(d)
    assert r['trade_ready'] is True
    assert 'EXECUTION_COST_EVIDENCE_INVALID' not in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['net_rr_after_costs']['reason']=='EXECUTION_COST_EVIDENCE_INVALID'


def test_final_gate_cannot_promote_explicit_macro_opposition_wait():
    d = base_row(
        symbol='LINKUSDT',
        htf_thesis={
            'status':'WAIT',
            'reason':'1D_MACRO_STRONGLY_OPPOSES_HTF',
            'product_direction':'SHORT',
            'entry_confirmation_direction':'SHORT',
            'direction_alignment':'ALIGNED',
        },
        market_direction_gate={'pass':True,'reason':'BTC_REGIME_NOT_OPPOSING'},
    )
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'HTF_THESIS_1D_MACRO_STRONGLY_OPPOSES_HTF' in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['authoritative_context']['htf_thesis_status'] == 'WAIT'


def test_final_gate_cannot_promote_long_into_htf_resistance_wait():
    d = long_row('PULLBACK')
    d.update({
        'symbol':'LTCUSDT',
        'htf_thesis':{
            'status':'WAIT',
            'reason':'LONG_INTO_HTF_RESISTANCE',
            'product_direction':'LONG',
            'entry_confirmation_direction':'LONG',
            'direction_alignment':'ALIGNED',
        },
        'market_direction_gate':{'pass':True,'reason':'BTC_REGIME_NOT_OPPOSING'},
    })
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'HTF_THESIS_LONG_INTO_HTF_RESISTANCE' in r['final_trade_gate']['blockers']


def test_missing_htf_authority_fails_closed():
    d = base_row()
    d['htf_thesis'] = {}
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert 'HTF_THESIS_STATUS_MISSING' in r['final_trade_gate']['blockers']


def test_missing_btc_first_authority_fails_closed_for_altcoins():
    d = base_row(symbol='SOLUSDT')
    d.pop('market_direction_gate', None)
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert 'BTC_FIRST_GATE_MISSING' in r['final_trade_gate']['blockers']


def test_final_gate_rechecks_btc_first_for_altcoins():
    d = base_row(
        symbol='ETHUSDT',
        market_direction_gate={
            'pass':False,
            'reason':'BTC_REGIME_OPPOSES_ALT_DIRECTION',
            'btc_regime':'TREND_UP',
            'btc_confidence':81,
        },
    )
    r = guard.apply(d)
    assert r['trade_ready'] is False
    assert r['actionable_decision'] == 'WAIT'
    assert 'BTC_FIRST_BTC_REGIME_OPPOSES_ALT_DIRECTION' in r['final_trade_gate']['blockers']
    assert r['final_trade_gate']['btc_first_rechecked_at_final_gate'] is True


def test_resolved_conditional_neutral_htf_remains_eligible():
    d = base_row(
        symbol='ADAUSDT',
        direction_alignment='CONDITIONAL_ALIGNED_12H_NEUTRAL',
        htf_thesis={
            'status':'PASS',
            'reason':'HTF_CONDITIONAL_12H_NEUTRAL_ACCEPTED',
            'product_direction':'SHORT',
            'entry_confirmation_direction':'SHORT',
            'direction_alignment':'CONDITIONAL_ALIGNED',
        },
        market_direction_gate={'pass':True,'reason':'BTC_REGIME_NOT_OPPOSING'},
    )
    r = guard.apply(d)
    assert r['trade_ready'] is True
    assert r['final_trade_gate']['authoritative_context']['htf_thesis_status'] == 'PASS'
    assert r['final_trade_gate']['authoritative_context']['btc_first_pass'] is True


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    for t in tests:
        t()
    print(f'final trade ready guard tests: {len(tests)} passed')
