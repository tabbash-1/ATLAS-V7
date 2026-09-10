#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, os, pathlib, time, urllib.parse, urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
BASE=os.environ.get('ATLAS_ANALYST_CAPTURE_BASE','https://atlas-v7.onrender.com').rstrip('/')
SYMBOLS=tuple(x.strip().upper() for x in os.environ.get('ATLAS_ANALYST_CAPTURE_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ZECUSDT,HYPEUSDT').split(',') if x.strip())
OUT=pathlib.Path(os.environ.get('ATLAS_ANALYST_CAPTURE_OUT',str(ROOT/'status/history/analyst-output-snapshots.jsonl')))
CAPTURE_SCHEMA=os.environ.get('ATLAS_ANALYST_CAPTURE_SCHEMA','ATLAS_ANALYST_OUTPUT_FORWARD_CAPTURE_V1')
COHORT_LABEL=os.environ.get('ATLAS_ANALYST_CAPTURE_COHORT_LABEL','')
FREEZE_CANDIDATE_COSTS=os.environ.get('ATLAS_ANALYST_CAPTURE_FREEZE_CANDIDATE_COSTS','0').strip().lower() in ('1','true','yes','on')
EXPECTED='PRODUCT_QUALITY_GATE_V2_CANONICAL_ANALYST_OUTPUT'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ATLAS-Forward-Capture/1.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=90) as r:return json.loads(r.read().decode())
def valid(d,s):
    a=(d or {}).get('analyst_output') or {}
    return d.get('ok') is True and d.get('symbol')==s and d.get('canonical_product_contract')=='analyst_output' and d.get('quality_gate_version')==EXPECTED and a.get('contract_version')==EXPECTED and a.get('lane')=='CORE_4_12H' and a.get('horizon')=='4-12H' and a.get('decision') in ('LONG','SHORT','WAIT') and a.get('analysis_only') is True and a.get('live_execution') is False
def freeze_candidate_cost(d,s):
    if not FREEZE_CANDIDATE_COSTS:return
    gate=(d or {}).get('final_trade_gate') or ((d or {}).get('analyst_output') or {}).get('final_trade_gate') or {}
    cand=str((d or {}).get('candidate_direction') or gate.get('candidate_direction') or '').upper()
    if cand not in ('LONG','SHORT'):return
    try:
        from execution_cost_model import estimate
        snap=estimate(s)
        snap['captured_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        snap['freeze_role']='CANDIDATE_ENTRY_TIME_EVIDENCE_ONLY'
        snap['candidate_direction']=cand
        d['candidate_execution_cost_snapshot']=snap
    except Exception as exc:
        d['candidate_execution_cost_snapshot']={'validated':False,'blockers':['CANDIDATE_COST_CAPTURE_ERROR'],'error':str(exc)[:280],'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'freeze_role':'CANDIDATE_ENTRY_TIME_EVIDENCE_ONLY','candidate_direction':cand,'live_execution':False,'research_only':True}
def main():
    captured=dt.datetime.now(dt.timezone.utc).isoformat(); decisions={}; errors={}
    for s in SYMBOLS:
        ok=False
        for n in range(6):
            try:
                d=get(f"{BASE}/api/decision/current?symbol={urllib.parse.quote(s)}&t={time.time_ns()}")
                if not valid(d,s):raise RuntimeError('CANONICAL_CONTRACT_VALIDATION_FAILED')
                freeze_candidate_cost(d,s)
                decisions[s]=d; ok=True; break
            except Exception as e:
                errors[s]=str(e)[:280]; time.sleep(3)
        if ok: errors.pop(s,None)
    if not decisions:raise RuntimeError('NO_VALID_CANONICAL_DECISIONS')
    row={'schema':CAPTURE_SCHEMA,'captured_at':captured,'source':BASE,'contract_version':EXPECTED,'product_horizon':'4-12H','analysis_only':True,'live_execution':False,'decisions':decisions,'errors':errors}
    if COHORT_LABEL:row['cohort_label']=COHORT_LABEL
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('a',encoding='utf-8') as f:f.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({'captured_at':captured,'cohort_label':COHORT_LABEL or None,'source':BASE,'valid_symbols':sorted(decisions),'candidate_cost_freeze':FREEZE_CANDIDATE_COSTS,'errors':errors},sort_keys=True))
if __name__=='__main__':main()
