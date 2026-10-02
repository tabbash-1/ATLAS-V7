import profitability_prediction_drawdown_diagnostics as d
def test_contract():
    assert d.report({"priors":{"UP":1,"DOWN":1,"RANGE":1},"stats":{y:{f:(0,1) for f in __import__("profitability_prediction_engine").FEATURES} for y in ("UP","DOWN","RANGE")}},[])["contract"]["holdout_read"] is False
