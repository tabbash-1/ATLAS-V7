import json
from datetime import datetime,timezone,timedelta
import market_context_forward_ledger as l
import market_context_settlement as s
def test_capture_dedup_and_append_only_settlement(tmp_path):
 cap=tmp_path/"cap.jsonl";sett=tmp_path/"sett.jsonl";now=datetime.now(timezone.utc)
 ch={"decision":"LONG","reason":"x","version":"v","context":{}}
 r=l.capture(symbol="BTCUSDT",captured_at=(now-timedelta(hours=13)).isoformat(),price=100,champion_decision="WAIT",challenger=ch)
 assert l.append(r,cap) is True and l.append(r,cap) is False
 before=cap.read_text(); ev,err=s.settle_due([r],now=now,price_at=lambda sym,due:110,output=sett)
 assert not err and len(ev)==3 and cap.read_text()==before
 assert len(sett.read_text().splitlines())==3
 ev2,err=s.settle_due([r],now=now,price_at=lambda sym,due:120,output=sett)
 assert ev2==[] and len(sett.read_text().splitlines())==3
