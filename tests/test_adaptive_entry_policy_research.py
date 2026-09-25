import adaptive_entry_policy_research as m

def test_strong_setup_keeps_immediate_entry():
    r,p=m.choose(1.25,0.5,82)
    assert r==1.25 and p=="IMMEDIATE_STRONG_SETUP"

def test_lower_score_requires_delayed_path():
    r,p=m.choose(-1.0,0.4,74)
    assert r==0.4 and p=="DELAY_1H_CONFIRM"

def test_missing_delay_fails_closed():
    r,p=m.choose(-1.0,None,74)
    assert r is None and p=="UNEVALUABLE_DELAY_PATH"
