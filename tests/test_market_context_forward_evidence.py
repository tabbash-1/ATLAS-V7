from market_context_forward_ledger import capture,settle
from market_context_forward_evaluator import build
import json

def test_champion_and_challenger_are_frozen_before_settlement(tmp_path):
 c={"decision":"WAIT","reason":"OVEREXTENDED","version":"V","context":{"rsi":75}}
 x=capture(symbol="ZECUSDT",captured_at="2026-09-20T00:00:00Z",price=100,champion_decision="LONG",challenger=c)
 y=settle(x,{4:110,8:90,12:105})
 assert x["outcomes"]=={}
 assert y["outcomes"]["4"]["champion_directional_return"]==.1
 assert y["outcomes"]["4"]["challenger_directional_return"]==0
 assert y["production_effect"]=="NONE"

def test_evaluator_cannot_promote_even_with_positive_delta(tmp_path):
 p=tmp_path/"l.jsonl"
 rows=[]
 for i in range(30):
  x=capture(symbol="ZECUSDT",captured_at=f"2026-09-{i%20+1:02d}T00:00:00Z",price=100,champion_decision="WAIT",challenger={"decision":"LONG","reason":"X","version":"V"})
  rows.append(settle(x,{4:101,8:102,12:103}))
 p.write_text("\n".join(json.dumps(x) for x in rows))
 e=build(p)
 assert e["promotion_evidence_ready"] is True
 assert e["promotion_allowed"] is False
 assert e["automatic_promotion"] is False
 assert e["horizons"]["12"]["delta_avg"]>0
