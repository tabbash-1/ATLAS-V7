from datetime import datetime,timezone
from market_context_forward_ledger import capture
from market_context_settlement import settle_due
def test_settlement_only_uses_due_horizons(tmp_path):
 r=capture(symbol="ZECUSDT",captured_at="2026-09-20T00:00:00Z",price=100,champion_decision="LONG",challenger={"decision":"WAIT","reason":"X","version":"V"})
 seen=[]
 def price(s,t):seen.append(t.hour);return 110
 events,errors=settle_due([r],now="2026-09-20T09:00:00Z",price_at=price,output=tmp_path/"sett.jsonl")
 assert {x["horizon_h"] for x in events}=={4,8} and errors==[]
 assert seen==[4,8]
