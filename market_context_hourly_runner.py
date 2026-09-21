#!/usr/bin/env python3
"""Hourly-safe reasoning research runner: capture, settle, evaluate, publish status.

Uses existing ATLAS market-data functions. Research-only; never calls an execution path.
"""
from __future__ import annotations
import json,pathlib
from datetime import datetime,timezone
import atlas_runtime_server as runtime
atlas=runtime.atlas
import market_context_klines as context_klines
import market_context_cycle as cycle
import market_context_settlement as settlement
import market_context_forward_evaluator as evaluator
import market_context_status as status

ROOT=pathlib.Path(__file__).resolve().parent
SNAP=ROOT/"status/raw/decisions_all.json"; LEDGER=ROOT/"status/market-context-reasoning-ledger.jsonl"

def _load_snapshot():
 if not SNAP.exists(): raise RuntimeError("CANONICAL_SNAPSHOT_MISSING")
 x=json.loads(SNAP.read_text())
 if not x.get("decisions"): raise RuntimeError("CANONICAL_SNAPSHOT_EMPTY")
 return x

def _klines(symbol): return context_klines.load(symbol, interval="4h")

def _price_at(symbol,due):
 # Existing spot kline provider; choose first candle at/after due from returned history.
 ks=atlas._spot_klines(symbol)
 target=due.timestamp()*1000
 candidates=[]
 for k in ks:
  tm=k.get("open_time") or k.get("timestamp") or k.get("time")
  if tm is not None and float(tm)>=target:candidates.append((float(tm),float(k["close"])))
 if not candidates: raise RuntimeError("HORIZON_PRICE_NOT_AVAILABLE")
 return min(candidates,key=lambda z:z[0])[1]

def run(now=None):
 now=now or datetime.now(timezone.utc)
 snapshot=_load_snapshot()
 cap=cycle.run(snapshot=snapshot,kline_loader=_klines,now=now.isoformat(),output=LEDGER)
 rows=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()] if LEDGER.exists() else []
 events,errors=settlement.settle_due(rows,now=now,price_at=_price_at)

 ev=evaluator.build(LEDGER, settlement.ledger.SETTLEMENT_OUT)
 evaluator.OUT.write_text(json.dumps(ev,indent=2,sort_keys=True))
 st=status.build();status.OUT.write_text(json.dumps(st,indent=2,sort_keys=True))
 return {"capture":cap,"settled_n":len(events),"settlement_errors":errors,"evaluation":ev,"research_only":True,"production_effect":"NONE"}

if __name__=="__main__":
 print(json.dumps(run(),sort_keys=True))
