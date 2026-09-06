from htf_scenario_engine import build_scenario_from_context


def pa(status='BULLISH_CONFLUENCE'):
    return {
        'combined': {'status': status},
        'frames': {
            '4h': {
                'nearest_support_zone': {'low': 95.0, 'high': 96.0, 'mid': 95.5},
                'nearest_resistance_zone': {'low': 104.0, 'high': 105.0, 'mid': 104.5},
            },
            '12h': {
                'nearest_support_zone': {'low': 92.0, 'high': 94.0, 'mid': 93.0},
                'nearest_resistance_zone': {'low': 108.0, 'high': 110.0, 'mid': 109.0},
            },
        },
    }


def test_long_scenario_ready_without_decision_authority():
    thesis={'status':'PASS','direction':'LONG','reason':'HTF_ALIGNED'}
    row=build_scenario_from_context(thesis,pa())
    assert row['preferred_direction']=='LONG'
    assert row['readiness']=='CONDITIONAL_SCENARIO_READY'
    assert row['selected_case']['trigger_level']==105.0
    assert row['selected_case']['invalidation_level']==95.0
    assert row['can_override_canonical_decision'] is False
    assert row['can_mark_trade_ready'] is False
    assert row['live_execution'] is False


def test_conflict_forces_scenario_wait():
    thesis={'status':'PASS','direction':'LONG','reason':'HTF_ALIGNED'}
    row=build_scenario_from_context(thesis,pa('HTF_PRICE_ACTION_CONFLICT'))
    assert row['preferred_direction']=='WAIT'
    assert row['readiness']=='WAIT_FOR_PRICE_ACTION_RESOLUTION'
    assert row['selected_case'] is None


def test_opposing_price_action_blocks_preferred_path():
    thesis={'status':'PASS','direction':'SHORT','reason':'HTF_ALIGNED'}
    row=build_scenario_from_context(thesis,pa('BULLISH_CONFLUENCE'))
    assert row['preferred_direction']=='WAIT'
    assert row['reason']=='BULLISH_PRICE_ACTION_OPPOSES_SHORT_THESIS'


def test_htf_not_ready_means_wait():
    thesis={'status':'WAIT','direction':None,'reason':'4H_12H_NOT_ALIGNED'}
    row=build_scenario_from_context(thesis,pa('NO_STRONG_PRICE_ACTION_CONFLUENCE'))
    assert row['preferred_direction']=='WAIT'
    assert row['readiness']=='WAIT_FOR_HTF_ALIGNMENT'
    assert row['reason']=='4H_12H_NOT_ALIGNED'
