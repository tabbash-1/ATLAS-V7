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


def test_regime_ranking_and_entry_state_are_non_executing():
    rows=[
      {"symbol":"SOLUSDT","opportunity_state":"ARMED","direction":"LONG","score":65,"threshold":68,"rr_tp2":2.2,"geometry_valid":True,"execution_ready":False,"action":"WAIT","asset_regime":"TREND_UP","btc_regime":"TREND_UP"},
      {"symbol":"XRPUSDT","opportunity_state":"ARMED","direction":"LONG","score":67,"threshold":68,"rr_tp2":2.4,"geometry_valid":True,"execution_ready":False,"action":"WAIT","asset_regime":"TREND_DOWN","btc_regime":"TREND_UP"},
    ]
    x=m.build(rows)
    sol=next(r for r in x["ranked_universe"] if r["symbol"]=="SOLUSDT")
    xrp=next(r for r in x["ranked_universe"] if r["symbol"]=="XRPUSDT")
    assert sol["regime_alignment"]=="ALIGNED"
    assert xrp["regime_alignment"]=="OPPOSED"
    assert sol["entry_state"]=="ARMED"
    assert sol["radar_score"] > xrp["radar_score"]
    assert all(r["action"]=="WAIT" for r in x["ranked_universe"])
    assert x["safety"]["decision_source_of_truth"]=="FINAL_TRADE_GATE"
