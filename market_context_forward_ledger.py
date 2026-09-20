#!/usr/bin/env python3
"""Immutable prospective champion-vs-reasoning challenger evidence.

Capture and settlement are separate append-only event streams. This prevents
outcome settlement from rewriting the pre-outcome decision record.
"""
from __future__ import annotations
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/"status/market-context-reasoning-ledger.jsonl"
SETTLEMENT_OUT=ROOT/"status/market-context-reasoning-settlements.jsonl"
SCHEMA="ATLAS_REASONING_CHALLENGER_LEDGER_V2_IMMUTABLE"
def _u(v):return str(v or "").strip().upper()
def _id(symbol,captured_at,price,champion,challenger):
 raw=json.dumps([_u(symbol),captured_at,float(price),_u(champion),_u(challenger)],separators=(",",":"))
 return hashlib.sha256(raw.encode()).hexdigest()[:24]
def directional_return(entry,exit_price,decision):
 if decision=="WAIT":return 0.0
 raw=float(exit_price)/float(entry)-1.0
 return raw if decision=="LONG" else -raw
def capture(*,symbol,captured_at,price,champion_decision,challenger):
 cd=_u(challenger.get("decision")); oid=_id(symbol,captured_at,price,champion_decision,cd)
 return {"schema":SCHEMA,"observation_id":oid,"symbol":_u(symbol),"captured_at":captured_at,"entry_price":float(price),
 "champion_decision":_u(champion_decision),"challenger_decision":cd,"challenger_reason":challenger.get("reason"),
 "challenger_version":challenger.get("version"),"context":challenger.get("context"),"research_only":True,"production_effect":"NONE","live_execution":False}
def append(row,path=OUT):
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  for line in path.read_text().splitlines():
   try:
    if json.loads(line).get("observation_id")==row.get("observation_id"):return False
   except:pass
 with path.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")
 return True
def append_settlement(row,path=SETTLEMENT_OUT):
 path.parent.mkdir(parents=True,exist_ok=True)
 key=(row["observation_id"],int(row["horizon_h"]))
 if path.exists():
  for line in path.read_text().splitlines():
   try:
    x=json.loads(line)
    if (x.get("observation_id"),int(x.get("horizon_h"))) == key:return False
   except:pass
 with path.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")
 return True
