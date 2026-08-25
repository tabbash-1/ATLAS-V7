import decision_engine_v7 as engine


def test_actionable_state_requires_execution_ready():
    assert engine.opportunity_state('LONG', True, True, 'ACTIONABLE') == 'ACTIONABLE'


def test_qualified_conditional_setup_is_armed_not_plain_wait():
    assert engine.opportunity_state('LONG', True, False, 'CONDITIONAL') == 'ARMED'
    assert engine.opportunity_state('SHORT', True, False, 'CONDITIONAL') == 'ARMED'


def test_unqualified_direction_remains_watch():
    assert engine.opportunity_state('LONG', False, False, 'CONDITIONAL') == 'WATCH'


def test_no_direction_is_no_setup():
    assert engine.opportunity_state(None, False, False, 'WAIT') == 'NO_SETUP'
