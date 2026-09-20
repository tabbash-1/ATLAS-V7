import market_context_status as s
def test_status_never_claims_production_authority():
 x=s.build()
 assert x["production_effect"]=="NONE"
 assert x["automatic_promotion"] is False
 assert x["research_only"] is True and x["live_execution"] is False
 assert "FINAL_TRADE_GATE" in x["warning"]
