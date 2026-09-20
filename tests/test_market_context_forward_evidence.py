import json
from datetime import datetime,timezone,timedelta
import market_context_forward_ledger as l
import market_context_settlement as s
from market_context_forward_evaluator import build
def test_immutable_capture_and_settlement(tmp_path):
 cap=tmp_path/"cap.jsonl";sett=tmp_path/"sett.jsonl";now=datetime.now(timezone.utc)
 x=l.capture(symbol="ZECUSDT",captured_at=(now-timedelta(hours=13)).isoformat(),price=100,champion_decision="LONG",challenger={"decision":"WAIT","reason":"OVEREXTENDED","version":"V","context":{"rsi":75}})
 l.append(x,cap);before=cap.read_text();ev,err=s.settle_due([x],now=now,price_at=lambda sym,due:110,output=sett)
 assert not err and len(ev)==3 and cap.read_text()==before
 e=build(cap,sett);assert e["horizons"]["4"]["paired_n"]==1 and e["horizons"]["4"]["champion_avg"]==.1 and e["horizons"]["4"]["challenger_avg"]==0
def test_evaluator_never_auto_promotes(tmp_path):
 cap=tmp_path/"c";sett=tmp_path/"s"
 for i in range(30):
  x=l.capture(symbol="ZECUSDT",captured_at=f"2026-09-{i%20+1:02d}T{i%24:02d}:00:00Z",price=100,champion_decision="WAIT",challenger={"decision":"LONG","reason":"X","version":"V"})
  l.append(x,cap)
  for h,p in ((4,101),(8,102),(12,103)):
   l.append_settlement({"observation_id":x["observation_id"],"symbol":"ZECUSDT","horizon_h":h,"exit_price":p,"champion_directional_return":0,"challenger_directional_return":p/100-1},sett)
 e=build(cap,sett);assert e["promotion_evidence_ready"] is True and e["promotion_allowed"] is False and e["automatic_promotion"] is False
