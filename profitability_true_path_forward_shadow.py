"""Append-only true-path forward shadow contract. No Production authority."""
import json,datetime as dt
from pathlib import Path
SCHEMA="ATLAS_TRUE_PATH_FORWARD_SHADOW_V1"

def candidate(symbol,t,side,entry,stop,tp,p_tp,expected_r,model_version,feature_version):
 return {"schema":SCHEMA,"recorded_at":dt.datetime.now(dt.timezone.utc).isoformat(),"decision_t":int(t),"symbol":symbol,"side":side,"entry":float(entry),"stop":float(stop),"tp":float(tp),"p_tp_before_sl":float(p_tp),"p_sl_before_tp":1-float(p_tp),"expected_r":float(expected_r),"model_version":model_version,"feature_version":feature_version,"settlement":"PENDING","horizon_h":12,"research_only":True,"can_override_production":False}

def append(path,row):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("a") as f:f.write(json.dumps(row,sort_keys=True)+"\n")

def safety():return {"research_only":True,"strict_forward":True,"historical_backfill_can_qualify":False,"live_execution":False,"production_impact":"NONE","threshold":68,"can_override_final_gate":False}
