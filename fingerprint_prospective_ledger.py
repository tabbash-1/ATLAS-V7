#!/usr/bin/env python3
"""Append-only evidence ledger for the preregistered winning fingerprint.

A row is FORMAL_PROSPECTIVE only when ATLAS first records the assignment while
the canonical paper trade is still unresolved. Historical rows may be retained
as BACKFILL_BASELINE, but they are never eligible for formal prospective claims.
"""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
from winning_setup_fingerprint import RULE,match,MIN_MATCHED,MIN_CONTROL
VERSION="ATLAS_FINGERPRINT_PROSPECTIVE_LEDGER_V2"
FORMAL="FORMAL_PROSPECTIVE"
BACKFILL="BACKFILL_BASELINE"
def _read(p,default):
 try:return json.loads(p.read_text())
 except:return default
def _unresolved(r):
 s=r.get("settlement")
 if isinstance(s,dict) and s.get("terminal") is True:return False
 if r.get("outcome_known_at_entry") is True:return False
 cps=r.get("product_window_checkpoints") or []
 if any(x.get("matured") is True for x in cps if isinstance(x,dict)):return False
 return True
def build(root:Path):
 src=_read(root/"status/production-validation-latest.json",{});old=_read(root/"status/fingerprint-prospective-ledger.json",{"entries":[]})
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 byid={x["decision_id"]:x for x in old.get("entries",[]) if x.get("decision_id")}
 for r in src.get("rows") or []:
  did=r.get("decision_id") or r.get("id");p=r.get("decision_provenance")
  if not did or did in byid or not isinstance(p,dict) or p.get("frozen_before_outcome") is not True:continue
  cls=FORMAL if _unresolved(r) else BACKFILL
  byid[did]={"decision_id":did,"captured_at":r.get("captured_at"),"first_seen_at":now,"symbol":r.get("symbol"),"direction":r.get("direction"),"fingerprint_group":"MATCHED" if match(p) else "CONTROL","assignment_frozen_before_outcome":True,"evidence_class":cls,"first_seen_unresolved":cls==FORMAL,"outcome":None}
 entries=sorted(byid.values(),key=lambda x:(x.get("captured_at") or "",x["decision_id"]))
 formal=[x for x in entries if x.get("evidence_class")==FORMAL]
 return {"schema":VERSION,"generated_at":now,"rule":RULE,"minimums":{"matched":MIN_MATCHED,"control":MIN_CONTROL},"entries":entries,
 "counts":{"matched":sum(x["fingerprint_group"]=="MATCHED" for x in entries),"control":sum(x["fingerprint_group"]=="CONTROL" for x in entries),
 "formal_matched":sum(x["fingerprint_group"]=="MATCHED" for x in formal),"formal_control":sum(x["fingerprint_group"]=="CONTROL" for x in formal),"backfill":sum(x.get("evidence_class")!=FORMAL for x in entries)},
 "governance":{"formal_evaluation_requires_first_seen_unresolved":True,"backfill_excluded_from_formal_evaluation":True},
 "safety":{"append_only_identity":True,"outcome_cannot_change_assignment":True,"research_only":True,"can_override_production":False,"automatic_strategy_change":False}}
def validate(x):
 ids=[e["decision_id"] for e in x["entries"]];assert len(ids)==len(set(ids));assert all(e["assignment_frozen_before_outcome"] for e in x["entries"]);assert all(e.get("evidence_class") in {FORMAL,BACKFILL} for e in x["entries"]);assert not x["safety"]["can_override_production"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/fingerprint-prospective-ledger.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"counts":x["counts"]},sort_keys=True))
