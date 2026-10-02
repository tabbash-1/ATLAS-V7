import profitability_transition_predictor as p
def test_probability_and_safety():
 s=[{"x":{f:float(i%3) for f in p.FEATURES},"y":("EXPAND_UP","EXPAND_DOWN","NO_EXPANSION")[i%3]} for i in range(30)]
 q=p.predict(p.fit(s),s[0]["x"])
 assert abs(sum(q["probabilities"].values())-1)<1e-9
 assert p.safety()["future_features"] is False and p.safety()["threshold"]==68
