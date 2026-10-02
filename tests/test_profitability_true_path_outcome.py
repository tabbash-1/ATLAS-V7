from profitability_trade_outcome_predictor import outcome
import profitability_true_path_outcome as tp

def candle(t,o,h,l,c,v=1): return {"t":t,"o":o,"h":h,"l":l,"c":c,"v":v}

def test_tp_before_sl_and_sl_before_tp():
    e=100;a=10
    assert outcome(e,a,"UP",[candle(1,100,131,99,120)])==1
    assert outcome(e,a,"UP",[candle(1,100,101,84,90)])==0

def test_same_candle_is_conservative_loss():
    assert outcome(100,10,"UP",[candle(1,100,131,84,100)])==0

def test_neither_hit_is_explicit_unresolved():
    assert outcome(100,10,"UP",[candle(i,100,110,90,100) for i in range(1,13)]) is None

def test_safety_contract_locked():
    s=tp.safety()
    assert s["threshold"]==68
    assert s["production_impact"]=="NONE"
    assert s["purge_hours"]==12
    assert s["can_override_final_gate"] is False
