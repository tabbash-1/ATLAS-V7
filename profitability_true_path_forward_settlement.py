#!/usr/bin/env python3
"""Settle append-only true-path forward records after 12h. Research only."""
import json,time
from pathlib import Path
import profitability_trade_outcome_predictor as op
import profitability_true_path_metrics as metrics
import historical_core_4_12h_replay as core
H=3600000

def settle_row(z,now_ms=None,fetch=core.fetch_1h):
 if z.get("settlement")!="PENDING": return z
 now_ms=int(now_ms or time.time()*1000);t=int(z["decision_t"])
 if now_ms<t+12*H:return z
 rows=fetch(z["symbol"],2,now_ms)
 future=[r for r in rows if t<r["t"]<=t+12*H][:12]
 if len(future)<12:return z
 entry=float(z["entry"]);stop=float(z["stop"]);risk=abs(entry-stop)
 if risk<=0:return dict(z,settlement="INVALID",settled_at_ms=now_ms)
 atr=risk/1.5;y=op.outcome(entry,atr,z["side"],future)
 if y is None:return dict(z,settlement="UNRESOLVED",settled_at_ms=now_ms,outcome=None,net_r=0.0)
 return dict(z,settlement="WIN" if y==1 else "LOSS",settled_at_ms=now_ms,outcome=y,net_r=round(metrics.net_r(y,entry,atr),6))

def settle_file(path):
 p=Path(path)
 if not p.exists():return {"rows":0,"changed":0}
 rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()];out=[];changed=0
 for z in rows:
  q=settle_row(z);changed+=q!=z;out.append(q)
 if changed:p.write_text("\n".join(json.dumps(x,sort_keys=True) for x in out)+"\n")
 return {"rows":len(out),"changed":changed,"research_only":True,"production_impact":"NONE"}
if __name__=="__main__":print(json.dumps(settle_file("status/history/profitability-true-path-forward.jsonl"),sort_keys=True))
