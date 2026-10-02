import profitability_pipeline_historical_exam as m

def test_summary_math_and_safety_shape():
    rows=[{"settled":True,"r":2,"tradeable_opportunity":True,"atlas_captured":True,"detection_latency_min":0,"entry_efficiency":1},
          {"settled":True,"r":-1,"tradeable_opportunity":True,"atlas_captured":True,"detection_latency_min":0,"entry_efficiency":1}]
    x=m.summarize(rows)
    assert x["net_r"]==1 and x["avg_r"]==.5 and x["profit_factor_r"]==2
    assert x["max_drawdown_r"]==1
