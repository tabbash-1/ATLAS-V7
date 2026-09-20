import market_context_klines as m
def test_explicit_4h_request(monkeypatch):
 seen={}
 def fake(urls,kind):
  seen["urls"]=urls;return [[1,"1","2",".5","1.5","10"]]
 monkeypatch.setattr(m.atlas,"get_json_fallback",fake)
 x=m.load("BTCUSDT","4h",220)
 assert all("interval=4h" in u for u in seen["urls"])
 assert x[0]["interval"]=="4h"
