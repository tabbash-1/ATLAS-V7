#!/usr/bin/env python3
"""Settle due 4/8/12H reasoning observations using timestamped price lookup."""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
import market_context_forward_ledger as ledger

def ts(v):
 d=datetime.fromisoformat(str(v).replace("Z","+00:00"));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def settle_due(rows, *, now, price_at):
 now=ts(now) if not isinstance(now,datetime) else now
 out=[];errors=[]
 for row in rows:
  x=json.loads(json.dumps(row)); captured=ts(x["captured_at"]); prices={}
  for h in (4,8,12):
   if str(h) in (x.get("outcomes") or {}): continue
   due=captured+timedelta(hours=h)
   if now<due: continue
   try:
    p=price_at(x["symbol"],due)
    if p is not None: prices[h]=float(p)
   except Exception as exc: errors.append({"symbol":x["symbol"],"horizon_h":h,"reason":str(exc)})
  if prices:x=ledger.settle(x,prices)
  out.append(x)
 return out,errors

def rewrite(rows,path=ledger.OUT):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in rows))
