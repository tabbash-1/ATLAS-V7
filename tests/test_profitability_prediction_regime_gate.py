import profitability_prediction_regime_gate as g
def test_gate():
 assert g.allow("UP",{"asset_regime":"TREND_UP","btc_regime":"TREND_UP"})
 assert not g.allow("UP",{"asset_regime":"TREND_UP","btc_regime":"BREAKDOWN_DOWN"})
 assert not g.allow("DOWN",{"asset_regime":"TRANSITION","btc_regime":"TREND_DOWN"})
 assert g.safety()["threshold"]==68
