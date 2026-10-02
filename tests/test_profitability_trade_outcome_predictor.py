import profitability_trade_outcome_predictor as p
def test_ev_math_and_safety():
 x={f:0.0 for f in p.FEATURES};m=p.fit([{"x":x,"y":1},{"x":x,"y":0}]);q=p.predict(m,x)
 assert abs(q["p_tp_before_sl"]+q["p_sl_before_tp"]-1)<1e-9
 assert abs(q["expected_r"]-.5)<1e-9
 assert p.safety()["future_features"] is False and p.safety()["threshold"]==68
