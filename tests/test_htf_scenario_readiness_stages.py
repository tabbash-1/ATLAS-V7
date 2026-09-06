import htf_scenario_engine as e


def thesis(direction='LONG', status='PASS'):
    return {'status': status, 'direction': direction, 'reason': 'x'}


def pa(status):
    frame={'nearest_resistance_zone':{'high':110},'nearest_support_zone':{'low':90}}
    return {'combined':{'status':status},'frames':{'4h':frame,'12h':frame}}


def test_long_neutral_is_watch():
    out=e.build_scenario_from_context(thesis('LONG'),pa('NO_STRONG_PRICE_ACTION_CONFLUENCE'))
    assert out['readiness']=='WATCH_SCENARIO'
    assert out['scenario_stage']=='WATCH'
    assert out['preferred_direction']=='LONG'
    assert out['price_action_confirmed'] is False


def test_long_matching_pa_is_armed():
    out=e.build_scenario_from_context(thesis('LONG'),pa('BULLISH_CONFLUENCE'))
    assert out['readiness']=='CONDITIONAL_SCENARIO_READY'
    assert out['scenario_stage']=='ARMED'
    assert out['price_action_confirmed'] is True


def test_short_matching_pa_is_armed():
    out=e.build_scenario_from_context(thesis('SHORT'),pa('BEARISH_CONFLUENCE'))
    assert out['readiness']=='CONDITIONAL_SCENARIO_READY'
    assert out['scenario_stage']=='ARMED'


def test_opposite_pa_forces_wait():
    out=e.build_scenario_from_context(thesis('LONG'),pa('BEARISH_CONFLUENCE'))
    assert out['preferred_direction']=='WAIT'
    assert out['scenario_stage']=='WAIT'
    assert out['readiness']=='WAIT_FOR_PRICE_ACTION_RESOLUTION'


def test_safety_contract_unchanged():
    out=e.build_scenario_from_context(thesis('LONG'),pa('BULLISH_CONFLUENCE'))
    assert out['version']=='HTF_SCENARIO_ENGINE_V1'
    assert out['readiness_classification_version']=='HTF_SCENARIO_READINESS_STAGES_V1'
    assert out['can_change_score'] is False
    assert out['can_change_threshold'] is False
    assert out['can_override_canonical_decision'] is False
    assert out['can_mark_trade_ready'] is False
    assert out['live_execution'] is False


if __name__=='__main__':
    test_long_neutral_is_watch(); test_long_matching_pa_is_armed(); test_short_matching_pa_is_armed(); test_opposite_pa_forces_wait(); test_safety_contract_unchanged()
    print('HTF scenario readiness stage tests: OK')
