#!/usr/bin/env python3
"""ATLAS Profitability stages 8-9: strict forward shadow + promotion gate."""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
VERSION="ATLAS_PROFITABILITY_FORWARD_PROMOTION_V1"
MIN_N=30; MIN_AVG_R=0.10; MIN_PF=1.20; MAX_DD_R=6.0; MIN_CAPTURE=0.50

def evaluate(edge, replay):
    o=(edge or {}).get("overall") or {}; k=(replay or {}).get("kpis") or replay or {}
    n=int(o.get("n") or 0); avg=o.get("avg_r"); pf=o.get("profit_factor_r")
    dd=(edge or {}).get("max_drawdown_r")
    capture=k.get("opportunity_capture_rate")
    checks={
      "sample_n": n>=MIN_N,
      "avg_r": avg is not None and float(avg)>=MIN_AVG_R,
      "profit_factor": pf is not None and float(pf)>=MIN_PF,
      "max_drawdown": dd is not None and float(dd)<=MAX_DD_R,
      "opportunity_capture": capture is not None and float(capture)>=MIN_CAPTURE,
    }
    proven=all(checks.values())
    return {"schema":VERSION,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
      "state":"PROMOTION_ELIGIBLE" if proven else "FORWARD_SHADOW_COLLECTING",
      "checks":checks,"observed":{"n":n,"avg_r":avg,"profit_factor_r":pf,"max_drawdown_r":dd,
      "opportunity_capture_rate":capture},
      "locked_rules":{"min_n":MIN_N,"min_avg_r":MIN_AVG_R,"min_profit_factor_r":MIN_PF,
      "max_drawdown_r":MAX_DD_R,"min_opportunity_capture_rate":MIN_CAPTURE},
      "promotion":{"automatic":False,"requires_new_reviewed_pr":True,
      "production_change_allowed_by_this_module":False},
      "safety":{"research_only":True,"paper_only":True,"live_execution":False,
      "can_override_production":False,"can_change_threshold":False,"production_threshold":68,
      "strict_forward_only":True,"historical_backfill_can_qualify":False}}

def build(root=Path(".")):
    def read(name):
        p=root/"status"/name
        return json.loads(p.read_text()) if p.exists() else {}
    edge=read("trade-edge-prospective-latest.json")
    replay=read("profitability-replay-latest.json")
    x=evaluate(edge,replay)
    out=root/"status"/"profitability-forward-promotion-latest.json"
    out.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
    return x

if __name__=="__main__": print(json.dumps(build(),sort_keys=True))
