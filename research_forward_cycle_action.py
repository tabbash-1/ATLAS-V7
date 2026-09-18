#!/usr/bin/env python3
import json
from pathlib import Path
import atlas_research_runtime_server as research
STATUS=Path("status"); STATUS.mkdir(exist_ok=True)
state=research.research_cloud_forward_cycle(); lane=research.RESEARCH_LANE_STATE
payload={"schema":"ATLAS_RESEARCH_FORWARD_CYCLE_V1","research_only":True,"live_execution":False,"can_override_production":False,"changes_production_universe":False,"changes_threshold":False,"product_horizon":"4-12H","research_assets":list(research.research_asset_universe.symbols()),"cycle_state":state,"research_lane":lane}
(STATUS/"research-forward-cycle-latest.json").write_text(json.dumps(payload,indent=2,sort_keys=True))
print(json.dumps({"selected":lane.get("last_selected"),"scored":lane.get("last_scored_symbols"),"failed":lane.get("last_failed_symbols")},indent=2))
