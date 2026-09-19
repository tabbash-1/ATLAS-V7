#!/usr/bin/env python3
"""Append-only prospective ledger for the preregistered winning fingerprint.
Freezes match/control assignment at entry before outcomes are known.
"""
from __future__ import annotations
import json,datetime as dt
from pathlib import Path
from winning_setup_fingerprint import RULE,match,MIN_MATCHED,MIN_CONTROL
VERSION="ATLAS_FINGERPRINT_PROSPECTIVE_LEDGER_V1"
def _read(p,default):
 try:return json.loads(p.read_text())
 except:return default
def build(root:Path):
 src=_read(root/"status/production-validation-latest.json",{});old=_read(root/"status/fingerprint-prospective-ledger.json",{"entries":[]})
 byid={x["decision_id"]:x for x in old.get("entries",[]) if x.get("decision_id")}
 for r in src.get("rows") or []:
  did=r.get("decision_id") or r.get("id");p=r.get("decision_provenance")
  if not did or did in byid or not isinstance(p,dict) or p.get("frozen_before_outcome") is not True:continue
  byid[did]={"decision_id":did,"captured_at":r.get("captured_at"),"symbol":r.get("symbol"),"direction":r.get("direction"),"fingerprint_group":"MATCHED" if match(p) else "CONTROL","assignment_frozen_before_outcome":True,"outcome":None}
 entries=sorted(byid.values(),key=lambda x:(x.get("captured_at") or "",x["decision_id"]))
 return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"rule":RULE,"minimums":{"matched":MIN_MATCHED,"control":MIN_CONTROL},"entries":entries,"counts":{"matched":sum(x["fingerprint_group"]=="MATCHED" for x in entries),"control":sum(x["fingerprint_group"]=="CONTROL" for x in entries)},"safety":{"append_only_identity":True,"outcome_cannot_change_assignment":True,"research_only":True,"can_override_production":False,"automatic_strategy_change":False}}
def validate(x):
 ids=[e["decision_id"] for e in x["entries"]];assert len(ids)==len(set(ids));assert all(e["assignment_frozen_before_outcome"] for e in x["entries"]);assert not x["safety"]["can_override_production"]
if __name__=="__main__":
 root=Path(__file__).resolve().parent;x=build(root);validate(x);(root/"status/fingerprint-prospective-ledger.json").write_text(json.dumps(x,indent=2,sort_keys=True)+"\n");print(json.dumps({"ok":True,"counts":x["counts"]},sort_keys=True))
