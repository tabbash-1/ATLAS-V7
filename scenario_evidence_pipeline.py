"""Collect, settle and calibrate ATLAS HTF scenario evidence.

Research-only GitHub Actions pipeline. WATCH and ARMED observations are both
frozen so the value of price-action confirmation can be measured separately.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os
from pathlib import Path
import urllib.parse, urllib.request
import scenario_outcome_calibration as calibration
import scenario_outcome_recorder as recorder

VERSION='SCENARIO_EVIDENCE_PIPELINE_V1'
BASE_URL=os.environ.get('ATLAS_BASE_URL','https://atlas-v7.onrender.com').rstrip('/')
SYMBOLS=tuple(x.strip().upper() for x in os.environ.get('ATLAS_SCENARIO_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ZECUSDT').split(',') if x.strip())
STATUS_DIR=Path(os.environ.get('ATLAS_SCENARIO_STATUS_DIR','status')); OUTCOMES_PATH=STATUS_DIR/'scenario-outcomes.json'; CALIBRATION_PATH=STATUS_DIR/'scenario-calibration-latest.json'; HISTORY_PATH=STATUS_DIR/'history'/'scenario-calibration.jsonl'
UA='ATLAS-Scenario-Evidence/1.0'; MAX_RECORDS=1000
SPOT_HOSTS=('https://data-api.binance.vision','https://api-gcp.binance.com','https://api1.binance.com','https://api2.binance.com','https://api3.binance.com','https://api4.binance.com','https://api.binance.com')

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def iso(v):
    x=v if isinstance(v,dt.datetime) else dt.datetime.fromtimestamp(float(v)/1000.0,tz=dt.timezone.utc)
    if x.tzinfo is None: x=x.replace(tzinfo=dt.timezone.utc)
    return x.astimezone(dt.timezone.utc).isoformat()
def parse_iso(v):
    x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
    if x.tzinfo is None: x=x.replace(tzinfo=dt.timezone.utc)
    return x.astimezone(dt.timezone.utc)
def _get_json(url,timeout=45):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.loads(r.read().decode())
def _fallback_json(path):
    errors=[]
    for host in SPOT_HOSTS:
        try: return _get_json(host+path)
        except Exception as exc: errors.append(f'{urllib.parse.urlparse(host).netloc}: {exc}')
    raise RuntimeError('All Binance Spot kline providers failed: '+' | '.join(errors))
def fetch_decision(symbol):
    row=_get_json(f'{BASE_URL}/api/decision/current?symbol={urllib.parse.quote(symbol)}',timeout=60)
    if not isinstance(row,dict) or row.get('ok') is not True: raise RuntimeError(f'Invalid ATLAS decision payload for {symbol}')
    return row
def fetch_klines(symbol,interval,start_at,limit=1000,now=None):
    start_ms=int(parse_iso(start_at).timestamp()*1000); end_now=now or now_utc(); path=f'/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval={urllib.parse.quote(interval)}&startTime={start_ms}&limit={int(limit)}'; raw=_fallback_json(path)
    if not isinstance(raw,list): raise RuntimeError('Invalid Binance Spot kline payload')
    rows=[]; now_ms=int(end_now.timestamp()*1000)
    for x in raw:
        if not isinstance(x,list) or len(x)<7: continue
        close_ms=int(x[6])
        if close_ms>=now_ms: continue
        rows.append({'time':iso(close_ms),'close_time':iso(close_ms),'open':float(x[1]),'high':float(x[2]),'low':float(x[3]),'close':float(x[4]),'volume':float(x[5]),'closed':True})
    return rows

def scenario_geometry_key(record):
    raw='|'.join([str(record.get('scenario_version') or ''),str(record.get('symbol') or ''),str(record.get('direction') or ''),str(record.get('trigger_type') or ''),f"{float(record.get('trigger_level')):.8f}",f"{float(record.get('invalidation_level')):.8f}"])
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
def scenario_key(record):
    geometry=record.get('scenario_geometry_id') or scenario_geometry_key(record); stage=str(record.get('scenario_stage') or record.get('scenario_readiness') or 'LEGACY')
    return hashlib.sha256(f'{geometry}|{stage}'.encode()).hexdigest()[:24]

def capture_from_decision(decision,captured_at=None):
    row=recorder.capture(decision,captured_at=captured_at)
    if not row: return None
    sc=decision.get('htf_scenario_engine') or {}; readiness=sc.get('readiness'); stage=sc.get('scenario_stage')
    if readiness not in ('WATCH_SCENARIO','CONDITIONAL_SCENARIO_READY'): return None
    if stage not in ('WATCH','ARMED'): stage='ARMED' if readiness=='CONDITIONAL_SCENARIO_READY' else 'WATCH'
    row['scenario_readiness']=readiness; row['scenario_stage']=stage; row['readiness_classification_version']=sc.get('readiness_classification_version')
    row['scenario_geometry_id']=scenario_geometry_key(row); row['scenario_id']=scenario_key(row)
    row['frozen_context']={'canonical_product_decision':decision.get('canonical_product_decision'),'actionable_decision':decision.get('actionable_decision'),'score':decision.get('score'),'threshold':decision.get('threshold'),'analysis_ready':decision.get('analysis_ready'),'setup_ready':decision.get('setup_ready'),'scenario_readiness':readiness,'scenario_stage':stage,'htf_thesis_status':sc.get('htf_thesis_status'),'htf_thesis_direction':sc.get('htf_thesis_direction'),'price_action_status':sc.get('price_action_status')}
    row['pipeline_version']=VERSION; return row

def load_records(path=OUTCOMES_PATH):
    try:
        obj=json.loads(Path(path).read_text()); rows=obj.get('records') if isinstance(obj,dict) else obj; return list(rows or [])
    except Exception: return []
def dedupe_append(records,candidate):
    if not candidate: return False
    key=candidate.get('scenario_id') or scenario_key(candidate)
    if any((r.get('scenario_id') or scenario_key(r))==key for r in records): return False
    records.append(candidate); return True
def settle_record(row,now=None):
    if not row.get('captured_at') or not row.get('symbol'): return row
    out=recorder.settle(row,fetch_klines(str(row['symbol']).upper(),'4h',row['captured_at'],now=now))
    if out.get('triggered'): out=recorder.attach_forward_returns(out,fetch_klines(str(row['symbol']).upper(),'1h',out['triggered_at'],now=now))
    out['last_settled_at']=(now or now_utc()).isoformat(); return out
def calibration_snapshot(records,captured_at=None):
    stamp=captured_at or now_utc().isoformat(); return {'schema':'ATLAS_SCENARIO_CALIBRATION_SNAPSHOT_V1','pipeline_version':VERSION,'captured_at':stamp,'horizons':{str(h):calibration.calibrate(records,horizon=h) for h in (4,8,12)},'research_only':True,'live_execution':False,'production_changed':False}
def save(records,snapshot,status_dir=STATUS_DIR):
    status=Path(status_dir); history=status/'history'; history.mkdir(parents=True,exist_ok=True); records=records[-MAX_RECORDS:]
    (status/'scenario-outcomes.json').write_text(json.dumps({'schema':'ATLAS_SCENARIO_OUTCOMES_V1','pipeline_version':VERSION,'updated_at':snapshot['captured_at'],'record_count':len(records),'records':records,'research_only':True,'live_execution':False},indent=2,sort_keys=True)+'\n')
    (status/'scenario-calibration-latest.json').write_text(json.dumps(snapshot,indent=2,sort_keys=True)+'\n')
    with (history/'scenario-calibration.jsonl').open('a') as f: f.write(json.dumps(snapshot,separators=(',',':'),sort_keys=True)+'\n')
def run_once(now=None):
    stamp=(now or now_utc()).isoformat(); records=load_records(); captured=deduped=0; decision_errors=[]; settlement_errors=[]
    for symbol in SYMBOLS:
        try:
            candidate=capture_from_decision(fetch_decision(symbol),captured_at=stamp)
            if candidate:
                if dedupe_append(records,candidate): captured+=1
                else: deduped+=1
        except Exception as exc: decision_errors.append({'symbol':symbol,'error':str(exc)})
    settled=[]
    for row in records:
        try: settled.append(settle_record(row,now=now))
        except Exception as exc:
            copy=dict(row); copy['last_settlement_error']=str(exc); settled.append(copy); settlement_errors.append({'scenario_id':row.get('scenario_id'),'symbol':row.get('symbol'),'error':str(exc)})
    snapshot=calibration_snapshot(settled,captured_at=stamp); snapshot['collector']={'symbols':list(SYMBOLS),'captured_new':captured,'deduped':deduped,'records':len(settled),'decision_errors':decision_errors,'settlement_errors':settlement_errors}; save(settled,snapshot); return snapshot
if __name__=='__main__':
    result=run_once(); print(json.dumps({'ok':not result['collector']['decision_errors'] and not result['collector']['settlement_errors'],'pipeline_version':VERSION,'collector':result['collector'],'research_only':True,'live_execution':False},indent=2))
