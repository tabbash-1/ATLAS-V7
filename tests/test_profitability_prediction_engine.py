import profitability_prediction_engine as p
def test_split_is_chronological_and_holdout_closed():
    s=[{"t":i,"x":{f:float(i) for f in p.FEATURES},"y":("UP","DOWN","RANGE")[i%3]} for i in range(30)]
    tr,va,ho=p.chronological_split(s)
    assert max(x["t"] for x in tr)<min(x["t"] for x in va)<min(x["t"] for x in ho)
    m=p.fit(tr); q=p.predict(m,ho[0]["x"])
    assert abs(sum(q["probabilities"].values())-1)<1e-5
    assert p.safety()["holdout_used_for_fit"] is False and p.safety()["threshold"]==68
