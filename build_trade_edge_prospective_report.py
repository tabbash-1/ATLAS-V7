#!/usr/bin/env python3
"""Build the frozen ATLAS prospective edge report from committed settlements."""
import json, pathlib
from trade_edge_prospective_validation import evaluate

ROOT=pathlib.Path(__file__).resolve().parent
SOURCE=ROOT/"status/production-path-settlement-latest.json"
OUT=ROOT/"status/trade-edge-prospective-latest.json"
BASELINE_AT="2026-09-23T18:00:00+00:00"
BASELINE_COMMIT="1015a02dc8ab25d812249d55a5ac5e27410e82ed"

def main():
    raw=json.loads(SOURCE.read_text()) if SOURCE.exists() else {}
    report=evaluate(raw.get("records") or [],BASELINE_AT,BASELINE_COMMIT)
    report["source_schema"]=raw.get("schema")
    report["source_generated_at"]=raw.get("generated_at")
    report["source_file"]="status/production-path-settlement-latest.json"
    report["research_only"]=True
    report["can_override_production"]=False
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({"proof_status":report["proof_status"],"overall":report["overall"]},sort_keys=True))
if __name__=="__main__": main()
