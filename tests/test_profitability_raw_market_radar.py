import profitability_raw_market_radar as m

def candles(up=True,n=300):
 out=[]
 for i in range(n):
  c=100+i*.2 if up else 200-i*.2
  out.append({"t":i*3600000,"o":c-.05,"h":c+.2,"l":c-.2,"c":c,"v":200 if i==n-1 else 100})
 return out

def test_raw_radar_does_not_need_production_decisions():
 x=m.build({"BTCUSDT":candles(True),"SOLUSDT":candles(True)})
 assert x["btc_context"]["side"]=="LONG"
 assert x["ranked_universe"][0]["radar_score"]>0
 assert x["safety"]["can_create_trade"] is False
 assert x["safety"]["can_override_production"] is False

def test_btc_breakdown_blocks_alt_long():
 x=m.build({"BTCUSDT":candles(False),"SOLUSDT":candles(True)})
 sol=next(z for z in x["ranked_universe"] if z["symbol"]=="SOLUSDT")
 assert sol["state"]=="BLOCKED_BTC_BREAKDOWN"
