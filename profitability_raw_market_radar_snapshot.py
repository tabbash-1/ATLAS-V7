#!/usr/bin/env python3
import json,time
from pathlib import Path
from historical_core_4_12h_replay import fetch_1h
from profitability_raw_market_radar import build
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT","HYPEUSDT"]
now=(int(time.time()*1000)//3600000)*3600000
data={}
for s in SYMBOLS:
 try:data[s]=fetch_1h(s,14,now)
 except Exception as e:pass
out=build(data);out["generated_at_ms"]=now;out["requested_assets"]=len(SYMBOLS);out["scanned_assets"]=len(data)
p=Path("status/profitability-raw-market-radar-latest.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps(out["top_candidates"],sort_keys=True))
