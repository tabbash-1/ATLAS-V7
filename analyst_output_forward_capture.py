#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, pathlib, time, urllib.parse, urllib.request
BASE='https://atlas-v7.onrender.com'
SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','HYPEUSDT')
OUT=pathlib.Path(__file__).resolve().parent/'status/history/analyst-output-snapshots.jsonl'
EXPECTED='PRODUCT_QUALITY_GATE_V2_CANONICAL_ANALYST_OUTPUT'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ATLAS-Forward-Capture/1.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())
def valid(d,s):
    a=(d or {}).get('analyst_output') or {}
    return d.get('ok') is True and d.get('symbol')==s and d.get('canonical_product_contract')=='analyst_output' and d.get('quality_gate_version')==EXPECTED and a.get('contract_version')==EXPECTED and a.get('lane')=='CORE_4_12H' and a.get('horizon')=='4-12H' and a.get('decision') in ('LONG','SHORT','WAIT') and a.get('analysis_only') is True and a.get('live_execution') is False
def main():
    captured=dt.datetime.now(dt.timezone.utc).isoformat(); decisions={}; errors={}
    for s in SYMBOLS:
        ok=False
        for n in range(6):
            try:
                d=get(f"{BASE}/api/decision/current?symbol={urllib.parse.quote(s)}&t={time.time_ns()}")
                if not valid(d,s):raise RuntimeError('CANONICAL_CONTRACT_VALIDATION_FAILED')
                decisions[s]=d; ok=True; break
            except Exception as e:
                errors[s]=str(e)[:280]; time.sleep(3)
        if ok: errors.pop(s,None)
    if not decisions:raise RuntimeError('NO_VALID_CANONICAL_DECISIONS')
    row={'schema':'ATLAS_ANALYST_OUTPUT_FORWARD_CAPTURE_V1','captured_at':captured,'source':BASE,'contract_version':EXPECTED,'product_horizon':'4-12H','analysis_only':True,'live_execution':False,'decisions':decisions,'errors':errors}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'captured_at':captured,'valid_symbols':sorted(decisions),'errors':errors},sort_keys=True))
if __name__=='__main__':main()
