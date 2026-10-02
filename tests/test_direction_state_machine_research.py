from direction_state_machine_research import transition

def test_long_cannot_flip_directly_to_short():
    x=transition("EXPANSION_LONG",short_confirmed=True)
    assert x["state"]=="EXPANSION_LONG"
    assert x["actionable_direction"]=="LONG"
    assert x["direct_long_to_short_allowed"] is False

def test_exhaustion_then_reversal_becomes_wait_not_short():
    a=transition("EXPANSION_LONG",exhaustion=True)
    b=transition(a["state"],reversal_caution=True)
    assert a["state"]=="LONG_EXHAUSTION_CAUTION"
    assert b["state"]=="REVERSAL_CAUTION"
    assert b["actionable_direction"]=="WAIT"

def test_even_post_reversal_short_is_unvalidated():
    x=transition("REVERSAL_CAUTION",short_confirmed=True)
    assert x["state"]=="SHORT_UNVALIDATED"
    assert x["actionable_direction"]=="WAIT"
    assert x["short_execution_validated"] is False

def test_long_progression():
    a=transition("NEUTRAL",early_long=True)
    b=transition(a["state"],long_confirmed=True)
    c=transition(b["state"],expansion=True)
    assert [a["state"],b["state"],c["state"]]==["EARLY_LONG","CONFIRMED_LONG","EXPANSION_LONG"]

def test_reversal_enters_neutral_rebuild_not_long():
    x=transition("REVERSAL_CAUTION",rebuild=True)
    assert x["state"]=="NEUTRAL_REBUILD"
    assert x["actionable_direction"]=="WAIT"
    assert x["immediate_long_reentry_after_reversal_allowed"] is False

def test_rebuild_requires_breadth_recovery_before_early_long():
    hold=transition("NEUTRAL_REBUILD",early_long=True)
    recover=transition("NEUTRAL_REBUILD",breadth_recovered=True)
    assert hold["state"]=="NEUTRAL_REBUILD"
    assert recover["state"]=="EARLY_LONG"
