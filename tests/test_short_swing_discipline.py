import short_swing_discipline as m
def base():
 return {"direction":"LONG","btc_trend":"UP","trend_4h":"LONG","trend_1d":"LONG","structure_confirmed":True,"momentum":"LONG","volume_above_average":True,"derivatives_bias":"LONG","entry":100,"sl":95,"tp1":110,"tp2":115,"sl_basis":"STRUCTURE","net_rr":2.2,"confidence":78,"position_risk_pct":1.5,"leverage":2,"liquidation_price":80,"invalidation":"4H structure breaks"}
def test_valid_shadow_trade():
 x=m.evaluate(base());assert x["signal"]=="LONG" and len(x["confirmations"])>=3 and x["production_effect"]=="NONE"
def test_btc_breakdown_blocks_alt_long():
 d=base();d["btc_trend"]="BREAKDOWN";assert m.evaluate(d)["signal"]=="NO_TRADE"
def test_rr_and_confidence_fail_closed():
 d=base();d["net_rr"]=1.9;d["confidence"]=69;x=m.evaluate(d);assert x["signal"]=="NO_TRADE" and "NET_RR_LT_2" in x["blockers"]
def test_liquidation_must_be_beyond_stop():
 d=base();d["liquidation_price"]=97;assert m.evaluate(d)["signal"]=="NO_TRADE"
def test_missing_data_never_invented():
 x=m.evaluate({"direction":"LONG"});assert x["signal"]=="NO_TRADE" and x["entry"] is None
