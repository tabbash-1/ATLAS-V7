#!/usr/bin/env python3
"""Prospective champion-vs-reasoning challenger ledger.

Research-only. Captures both decisions before outcomes exist, then settles 4/8/12H
directional returns. Never mutates Production.
"""
from __future__ import annotations
import json, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/"status/market-context-reasoning-ledger.jsonl"
SCHEMA="ATLAS_REASONING_CHALLENGER_LEDGER_V1"

def _u(v): return str(v or "").strip().upper()
def directional_return(entry, exit_price, decision):
    if decision=="WAIT": return 0.0
    raw=(float(exit_price)/float(entry)-1.0)
    return raw if decision=="LONG" else -raw

def capture(*, symbol, captured_at, price, champion_decision, challenger):
    return {"schema":SCHEMA,"symbol":_u(symbol),"captured_at":captured_at,
      "entry_price":float(price),"champion_decision":_u(champion_decision),
      "challenger_decision":_u(challenger.get("decision")),"challenger_reason":challenger.get("reason"),
      "challenger_version":challenger.get("version"),"context":challenger.get("context"),
      "outcomes":{},"research_only":True,"production_effect":"NONE","live_execution":False}

def settle(row, prices):
    x=json.loads(json.dumps(row))
    for h in (4,8,12):
        p=prices.get(h)
        if p is None: continue
        x["outcomes"][str(h)]={"exit_price":float(p),
          "champion_directional_return":round(directional_return(x["entry_price"],p,x["champion_decision"]),8),
          "challenger_directional_return":round(directional_return(x["entry_price"],p,x["challenger_decision"]),8)}
    return x

def append(row,path=OUT):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")
