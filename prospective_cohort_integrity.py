#!/usr/bin/env python3
"""Append-only integrity ledger for the preregistered direction guardrail cohort."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA='ATLAS_PROSPECTIVE_DIRECTION_COHORT_INTEGRITY_V1'

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def row_hash(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def load_jsonl(path):
    out=[]
    if not path.exists():return out
    for line in path.read_text(errors='replace').splitlines():
        if line.strip():out.append(json.loads(line))
    return out

def validate(manifest_path,cohort_path,ledger_path):
    m=json.loads(manifest_path.read_text()); rows=load_jsonl(cohort_path)
    manifest_hash=m['manifest_hash']; start=m['cohort_start_at']
    ids=[]; hashes={}
    for r in rows:
        rid=str(r.get('id') or '')
        if not rid:raise RuntimeError('COHORT_ROW_ID_MISSING')
        if rid in hashes:raise RuntimeError('COHORT_DUPLICATE_ID')
        if r.get('manifest_hash')!=manifest_hash:raise RuntimeError('COHORT_MANIFEST_HASH_MISMATCH')
        if str(r.get('captured_at') or '') < str(start):raise RuntimeError('COHORT_PRESTART_ROW')
        if r.get('outcome_known_at_freeze') is not False:raise RuntimeError('COHORT_OUTCOME_FREEZE_VIOLATION')
        if r.get('research_only') is not True or r.get('shadow_only') is not True:raise RuntimeError('COHORT_SAFETY_FLAG_VIOLATION')
        ids.append(rid); hashes[rid]=row_hash(r)
    previous={}
    if ledger_path.exists():
        old=json.loads(ledger_path.read_text()); previous=old.get('row_hashes') or {}
        if old.get('manifest_hash')!=manifest_hash:raise RuntimeError('INTEGRITY_LEDGER_MANIFEST_CHANGED')
        for rid,h in previous.items():
            if rid not in hashes:raise RuntimeError(f'COHORT_ROW_DELETED:{rid}')
            if hashes[rid]!=h:raise RuntimeError(f'COHORT_ROW_MUTATED:{rid}')
    chain=''
    for rid in ids:chain=hashlib.sha256((chain+'|'+rid+'|'+hashes[rid]).encode()).hexdigest()
    out={'schema':SCHEMA,'manifest_hash':manifest_hash,'cohort_start_at':start,'research_only':True,'shadow_only':True,'live_execution':False,'can_override_production':False,'append_only_verified':True,'previous_row_count':len(previous),'row_count':len(rows),'new_row_count':len(rows)-len(previous),'row_hashes':hashes,'ordered_chain_sha256':chain or hashlib.sha256(b'EMPTY_COHORT').hexdigest()}
    ledger_path.parent.mkdir(parents=True,exist_ok=True); ledger_path.write_text(json.dumps(out,indent=2,sort_keys=True)); return out

def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest',default='status/prospective-direction-guardrail-manifest.json'); p.add_argument('--cohort',default='status/history/prospective-direction-guardrail-cohort.jsonl'); p.add_argument('--ledger',default='status/prospective-direction-guardrail-integrity.json'); a=p.parse_args(); out=validate(Path(a.manifest),Path(a.cohort),Path(a.ledger)); print(json.dumps({k:out[k] for k in ('manifest_hash','append_only_verified','previous_row_count','row_count','new_row_count','ordered_chain_sha256')},sort_keys=True))
if __name__=='__main__':main()
