#!/usr/bin/env python3
"""Build the web-readable profitability research snapshot from committed evidence."""
import datetime as dt,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(name):
 p=ROOT/"status"/name
 try:return json.loads(p.read_text())
 except Exception:return {}
def build():
 promo=read("profitability-forward-promotion-latest.json")
 multi=read("profitability-outcome-multi-era-latest.json")
 payload={"schema":"ATLAS_PROFITABILITY_SHADOW_WEB_V1","ok":True,
  "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
  "state":"RESEARCH_SHADOW","production_threshold":68,"research_only":True,
  "can_override_production":False,"live_execution":False,
  "forward_promotion":promo,
  "multi_era":multi,
  "methodology":{"outcome_label":"TP_BEFORE_SL_PATH","same_candle":"LOSS","purge_hours":12,
    "note":"Live probabilities remain unavailable until a true-path prospective model snapshot is generated."}}
 out=ROOT/"status"/"profitability-shadow-latest.json"
 out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
 return payload
if __name__=="__main__":print(json.dumps(build(),sort_keys=True))
