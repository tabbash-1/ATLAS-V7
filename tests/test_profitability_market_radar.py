import profitability_market_radar as m

def test_radar_surfaces_emerging_without_creating_trade():
    rows=[
      {"symbol":"SOLUSDT","opportunity_state":"ARMED","score":65,"threshold":68,"rr_tp2":2.2,"geometry_valid":True,"execution_ready":False,"action":"WAIT"},
      {"symbol":"BTCUSDT","opportunity_state":"NO_SETUP","score":67,"threshold":68,"rr_tp2":1.7,"geometry_valid":False,"execution_ready":False,"action":"WAIT"},
      {"symbol":"ETHUSDT","opportunity_state":"WATCH","score":62,"threshold":68,"rr_tp2":2.5,"geometry_valid":True,"execution_ready":False,"action":"WAIT"},
    ]
    x=m.build(rows)
    assert x["top_candidates"][0]["symbol"]=="SOLUSDT"
    assert x["summary"]=={"assets":3,"emerging":2,"actionable":0,"armed":1,"watch":1}
    assert all(r["action"]=="WAIT" for r in x["ranked_universe"])
    assert x["safety"]["can_create_trade"] is False
    assert x["safety"]["can_override_production"] is False
