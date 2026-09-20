from datetime import datetime,timezone,timedelta
from market_context_forward_ledger import capture
from market_context_settlement import settle_due
from market_context_cost_evaluation import compare

def test_settlement_only_uses_due_horizons():
 r=capture(symbol="ZECUSDT",captured_at="2026-09-20T00:00:00Z",price=100,champion_decision="LONG",challenger={"decision":"WAIT","reason":"X","version":"V"})
 seen=[]
 def price(s,t):seen.append(t.hour);return 110
 rows,errors=settle_due([r],now="2026-09-20T09:00:00Z",price_at=price)
 assert set(rows[0]["outcomes"])=={"4","8"} and errors==[]
 assert "12" not in rows[0]["outcomes"]

def test_costs_charge_only_executed_direction():
 o={"champion_directional_return":.02,"challenger_directional_return":0}
 x=compare(o,"LONG","WAIT",10)
 assert x["champion_net_return"]==.019
 assert x["challenger_net_return"]==0
 assert x["challenger_cost_return"]==0

def test_missing_cost_never_invents_net_result():
 o={"champion_directional_return":.02,"challenger_directional_return":.03}
 x=compare(o,"LONG","LONG",None)
 assert x["champion_net_return"] is None and x["cost_validated"] is False
