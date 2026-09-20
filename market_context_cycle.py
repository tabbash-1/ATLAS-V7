#!/usr/bin/env python3
"""Automated research-universe Market Context Reasoning capture cycle."""
from __future__ import annotations
import json, pathlib
from datetime import datetime, timezone
import research_asset_universe as universe
import market_context_adapter as adapter
import market_context_forward_ledger as ledger

ROOT=pathlib.Path(__file__).resolve().parent
STATUS=ROOT/"status/market-context-reasoning-cycle-latest.json"

def _decision(snapshot,symbol):
    d=(snapshot.get("decisions") or {}).get(symbol) or {}
    c=str(d.get("candidate_direction") or "").upper()
    canonical=str(((d.get("canonical_decision") or {}).get("decision") or d.get("decision") or "WAIT")).upper()
    frames=((d.get("htf_thesis") or {}).get("frames") or {})
    d4=str((frames.get("4H") or {}).get("direction") or "").upper()
    d12=str((frames.get("12H") or {}).get("direction") or "").upper()
    align="ALIGNED" if d4 in ("LONG","SHORT") and d4==d12 else "CONFLICT"
    return canonical,c,align

def run(*, snapshot, kline_loader, now=None, event_context=None, output=ledger.OUT):
    now=now or datetime.now(timezone.utc).isoformat()
    events=event_context or {}; captured=[]; failed=[]
    for symbol in universe.symbols():
        try:
            canonical,candidate,alignment=_decision(snapshot,symbol)
            ks=kline_loader(symbol)
            if not ks: raise RuntimeError("NO_4H_KLINES")
            direction=candidate if candidate in ("LONG","SHORT") else canonical
            if direction not in ("LONG","SHORT"): direction=""
            ev=events.get(symbol) or {}
            challenger=adapter.from_4h_klines(ks,trend_direction=direction,htf_alignment=alignment,
                event_risk=ev.get("event_risk","UNKNOWN"),catalyst_bias=ev.get("catalyst_bias","UNKNOWN"))
            px=float(ks[-1]["close"])
            row=ledger.capture(symbol=symbol,captured_at=now,price=px,champion_decision=canonical,challenger=challenger)
            ledger.append(row,output);captured.append({"symbol":symbol,"champion":canonical,"challenger":challenger["decision"],"reason":challenger["reason"]})
        except Exception as exc: failed.append({"symbol":symbol,"reason":str(exc)})
    return {"schema":"ATLAS_REASONING_CAPTURE_CYCLE_V1","captured":captured,"failed":failed,
      "captured_n":len(captured),"failed_n":len(failed),"research_only":True,"production_effect":"NONE","live_execution":False}

def main():
    # Offline runner intentionally requires an explicit snapshot/loader integration.
    # Production runtime wiring is separate so this module cannot silently alter trading.
    STATUS.parent.mkdir(parents=True,exist_ok=True)
    STATUS.write_text(json.dumps({"schema":"ATLAS_REASONING_CAPTURE_CYCLE_V1","state":"READY_FOR_RUNTIME_WIRING","research_only":True,"production_effect":"NONE"},indent=2))
if __name__=="__main__":main()
