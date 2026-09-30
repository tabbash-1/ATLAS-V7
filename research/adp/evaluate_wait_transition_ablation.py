#!/usr/bin/env python3
"""ADP ablation V1: test frozen transition features on WAIT forward outcomes."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/"status/wait-missed-opportunity-latest.json"
OUT=ROOT/"research/adp/wait_transition_ablation_v1.json"
FEATURES=["asset_regime_aligned","btc_regime_aligned","h1_aligned","h4_aligned"]

def stats(rows,h="4h"):
    vals=[r["horizons"][h]["directional_return_pct"] for r in rows if r.get("horizons",{}).get(h)]
    return {"n":len(vals),"positive_n":sum(v>0 for v in vals),
            "direction_accuracy_pct":round(100*sum(v>0 for v in vals)/len(vals),2) if vals else None,
            "mean_directional_return_pct":round(sum(vals)/len(vals),4) if vals else None}

def main():
    d=json.loads(SRC.read_text())
    rows=[r for r in d["records"] if r.get("horizons",{}).get("4h")]
    out={"schema":"ADP_WAIT_TRANSITION_ABLATION_V1","research_only":True,"production_effect":"NONE",
         "source_generated_at":d.get("generated_at"),"all":stats(rows),"features":{}}
    for f in FEATURES:
        out["features"][f]={"true":stats([r for r in rows if r.get("transition_evidence",{}).get(f) is True]),
                            "false":stats([r for r in rows if r.get("transition_evidence",{}).get(f) is False])}
    combo=[r for r in rows if r.get("transition_evidence",{}).get("asset_regime_aligned") is True
                         and r.get("transition_evidence",{}).get("btc_regime_aligned") is True
                         and r.get("transition_evidence",{}).get("h1_aligned") is True]
    out["triple_alignment"]=stats(combo)
    out["interpretation"]="Ablation is descriptive within the WAIT/HTF-conflict population. Do not generalize to trade-ready signals or Production."
    OUT.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out,indent=2))
if __name__=="__main__":main()
