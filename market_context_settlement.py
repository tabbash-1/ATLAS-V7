#!/usr/bin/env python3
"""Append-only settlement for due 4/8/12H reasoning observations."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import market_context_forward_ledger as ledger
def ts(v):
 d=datetime.fromisoformat(str(v).replace("Z","+00:00"));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
def existing(path=ledger.SETTLEMENT_OUT):
 out=set()
 if path.exists():
  import json
  for line in path.read_text().splitlines():
   try:
    x=json.loads(line);out.add((x.get("observation_id"),int(x.get("horizon_h"))))
   except:pass
 return out
def settle_due(rows,*,now,price_at,output=ledger.SETTLEMENT_OUT):
 now=ts(now) if not isinstance(now,datetime) else now; done=existing(output);events=[];errors=[]
 for x in rows:
  if not x.get("observation_id"):
   errors.append({"symbol":x.get("symbol"),"horizon_h":None,"reason":"LEGACY_NO_OBSERVATION_ID"})
   continue
  captured=ts(x["captured_at"])
  for h in (4,8,12):
   key=(x.get("observation_id"),h)
   if key in done or now<captured+timedelta(hours=h):continue
   try:
    p=price_at(x["symbol"],captured+timedelta(hours=h))
    if p is None:continue
    ev={"schema":"ATLAS_REASONING_SETTLEMENT_V1","observation_id":x["observation_id"],"symbol":x["symbol"],"horizon_h":h,
      "exit_price":float(p),"champion_directional_return":round(ledger.directional_return(x["entry_price"],p,x["champion_decision"]),8),
      "challenger_directional_return":round(ledger.directional_return(x["entry_price"],p,x["challenger_decision"]),8),"research_only":True}
    if ledger.append_settlement(ev,output):events.append(ev);done.add(key)
   except Exception as exc:errors.append({"symbol":x["symbol"],"horizon_h":h,"reason":str(exc)})
 return events,errors
