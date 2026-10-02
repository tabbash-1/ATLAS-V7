#!/usr/bin/env python3
"""Build the web-readable profitability research snapshot from committed evidence."""
import datetime as dt,json\nimport profitability_true_path_metrics as tm\nimport profitability_true_path_forward_shadow as fs
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
  "methodology":{"current_true_path_state":"COLLECTING","legacy_multi_era_label":"12H_ENDPOINT_PROXY_NOT_TRUE_PATH","outcome_label":"TP_BEFORE_SL_PATH","same_candle":"LOSS","purge_hours":tm.PURGE_HOURS,"embargo_hours":tm.EMBARGO_HOURS,"round_trip_cost_bps":tm.ROUND_TRIP_COST_BPS,"calibration_metrics":["BRIER","LOG_LOSS"],"forward_shadow_schema":fs.SCHEMA,
    "note":"Live probabilities remain unavailable until a true-path prospective model snapshot is generated."}}
 out=ROOT/"status"/"profitability-shadow-latest.json"
 out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
 return payload
if __name__=="__main__":print(json.dumps(build(),sort_keys=True))
