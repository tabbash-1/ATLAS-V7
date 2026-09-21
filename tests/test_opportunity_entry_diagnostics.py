from opportunity_entry_diagnostics import classify, summarize

def test_right_direction_but_blocked_is_missed_opportunity():
    d={"candidate_direction":"LONG","entry":100,"production_signal_qualified":False,"execution_ready":False,
       "blocking_gates":["HTF_DIRECTION"]}
    out=classify(d,{4:101.2,8:102.5,12:103.0})
    assert out["classification"]=="MISSED_OPPORTUNITY"
    assert out["direction_quality"]=="RIGHT"

def test_ready_trade_with_followthrough_is_correct():
    d={"candidate_direction":"SHORT","entry":100,"production_signal_qualified":True,"execution_ready":True}
    out=classify(d,{4:98.5,8:97.5,12:97.0})
    assert out["classification"]=="CORRECT_TRADE"

def test_ready_trade_wrong_direction_is_exposed():
    d={"candidate_direction":"LONG","entry":100,"production_signal_qualified":True,"execution_ready":True}
    out=classify(d,{4:98.8,8:98.0,12:97.5})
    assert out["classification"]=="WRONG_DIRECTION"

def test_summary_capture_rate():
    s=summarize([{"classification":"CORRECT_TRADE"},{"classification":"MISSED_OPPORTUNITY"},
                 {"classification":"CORRECT_TRADE"},{"classification":"NO_MEANINGFUL_EDGE"}])
    assert s["opportunity_capture_rate"]==0.6667
