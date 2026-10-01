#!/usr/bin/env python3
"""Build a point-in-time ADP direction-label dataset from committed ATLAS evidence.

Research-only. Reads status artifacts; never mutates Production.
"""
from __future__ import annotations
import csv, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"research/adp/atlas_direction_dataset.csv"

def load(path):
    with open(ROOT/path, encoding="utf-8") as f: return json.load(f)

def raw_sign(direction, directional_value):
    if directional_value is None: return None
    v=float(directional_value)
    return v if direction=="LONG" else -v

def label(v, band=0.0):
    if v is None: return "UNKNOWN"
    return "UP" if v>band else "DOWN" if v < -band else "NEUTRAL"

def portfolio_rows():
    d=load("status/paper-portfolio-10k-latest.json")
    for t in d.get("trades",[]):
        cps={int(x["checkpoint_h"]):x for x in t.get("product_window_checkpoints",[]) if x.get("matured")}
        # checkpoint r_multiple is direction-normalized; invert SHORT to recover raw market direction.
        for h in (4,8,12):
            cp=cps.get(h)
            if not cp: continue
            raw=raw_sign(t["direction"], cp.get("r_multiple"))
            yield {
                "source":"TRADE_READY","decision_id":t["id"],"captured_at":t["captured_at"],
                "symbol":t["symbol"],"atlas_direction":t["direction"],"score":t.get("score"),
                "horizon_h":h,"forward_direction":label(raw),"directional_proxy":raw,
                "market_regime":"","playbook":"","evidence_quality":"CANONICAL_PORTFOLIO"
            }

def wait_rows():
    d=load("status/wait-missed-opportunity-latest.json")
    rows=d.get("rows", d.get("decisions", []))
    for t in rows:
        for h in (4,8,12):
            hp=t.get("horizons",{}).get(f"{h}h",{})
            if not hp: continue
            # directional_return_pct is normalized to the candidate direction.
            raw=raw_sign(t.get("direction"), hp.get("directional_return_pct"))
            yield {
                "source":"WAIT","decision_id":t.get("decision_id",t.get("id")),"captured_at":t.get("captured_at"),
                "symbol":t.get("symbol"),"atlas_direction":t.get("direction"),"score":t.get("score"),
                "horizon_h":h,"forward_direction":label(raw),"directional_proxy":raw,
                "market_regime":t.get("v2_regime",""),"playbook":t.get("playbook",""),
                "evidence_quality":"WAIT_FORWARD_EVIDENCE"
            }

def main():
    rows=list(portfolio_rows())+list(wait_rows())
    rows.sort(key=lambda r:(r.get("captured_at") or "",r.get("decision_id") or "",r["horizon_h"]))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0]) if rows else []
    with open(OUT,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(json.dumps({"rows":len(rows),"decisions":len({r["decision_id"] for r in rows}),
                      "symbols":len({r["symbol"] for r in rows}),"output":str(OUT.relative_to(ROOT))},indent=2))
if __name__=="__main__": main()
