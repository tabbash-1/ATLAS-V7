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
  "methodology":{"current_true_path_state":"COLLECTING_FORWARD_ONLY","legacy_multi_era_label":"12H_ENDPOINT_PROXY_NOT_TRUE_PATH","outcome_label":"TP_BEFORE_SL_PATH","same_candle":"LOSS","purge_hours":12,"embargo_hours":12,"locked_fee_r":0.02,"locked_slippage_r":0.02,"calibration_metrics":["BRIER","LOG_LOSS"],
    "note":"True-path V2 methodology locks costs, 12h purge + 12h embargo, and calibration metrics. Live probabilities remain unavailable until untouched forward-only samples mature."}}
 out=ROOT/"status"/"profitability-shadow-latest.json"
 out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
 return payload
if __name__=="__main__":print(json.dumps(build(),sort_keys=True))
