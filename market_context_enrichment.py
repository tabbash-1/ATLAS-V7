"""Evidence-backed context enrichment for the Reasoning Challenger.

Consumes existing ATLAS derivatives/liquidity/Whale-10/event evidence only.
Missing evidence stays UNKNOWN; nothing is fabricated. Shadow-only.
"""
from __future__ import annotations

def _u(v): return str(v or "").upper()
def enrich(base, *, futures=None, whale=None, event=None):
 c=dict(base or {}); evidence=[]; pressures=[]
 f=futures or {}
 if f.get("futures_evidence_validated"):
  imb=float(f.get("orderbook_imbalance") or 0); ratio=float(f.get("taker_ratio") or 1); funding=float(f.get("funding_rate") or 0)
  c["derivatives_available"]=True;c["orderbook_imbalance"]=imb;c["taker_ratio"]=ratio;c["funding_rate"]=funding
  if imb>=.12 and ratio>=1.15:evidence.append("DERIVATIVES_BUY_PRESSURE")
  if imb<=-.12 and ratio<=.87:pressures.append("DERIVATIVES_SELL_PRESSURE")
  c["liquidity_bias"]="BID" if imb>=.12 else "ASK" if imb<=-.12 else "MIXED"
 else:c["derivatives_available"]=False;c["liquidity_bias"]="UNKNOWN"
 w=whale or {}
 if w.get("status")=="READY_RESEARCH_ONLY" and int(w.get("validated_entities") or 0)==10:
  c["whale10_consensus"]=_u(w.get("consensus"))
  if c["whale10_consensus"]=="ACCUMULATION":evidence.append("WHALE10_ACCUMULATION")
  elif c["whale10_consensus"]=="DISTRIBUTION":pressures.append("WHALE10_DISTRIBUTION")
 else:c["whale10_consensus"]="UNKNOWN"
 e=event or {}
 if e.get("source_quality") in ("PRIMARY","TIER1") and e.get("confirmed") is True:
  impact=float(e.get("impact_score") or 0); direction=_u(e.get("direction"))
  c["event_risk"]="HIGH" if impact>=80 else "MEDIUM" if impact>=60 else "LOW"
  c["catalyst_bias"]="POSITIVE" if direction=="POSITIVE" else "NEGATIVE" if direction=="NEGATIVE" else "UNKNOWN"
 else:
  c.setdefault("event_risk","UNKNOWN");c.setdefault("catalyst_bias","UNKNOWN")
 c["enrichment_evidence"]=evidence;c["enrichment_pressures"]=pressures
 c["enrichment_mode"]="EVIDENCE_ONLY_SHADOW";return c
