#!/usr/bin/env python3
"""ATLAS $10K prospective evaluator for the canonical analyst_output contract.

Evaluation only. Never routes orders, changes Production, changes thresholds, or
backfills decisions that predate the frozen cohort start.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, math, pathlib, time
from typing import Any
from offline_production_path_settlement import market_klines, event_from, excursions

ROOT=pathlib.Path(__file__).resolve().parent
MANIFEST=ROOT/'status/paper-portfolio-10k-analyst-manifest.json'
HISTORY=ROOT/'status/history/production-snapshots.jsonl'
COHORT=ROOT/'status/history/paper-portfolio-10k-analyst-cohort.jsonl'
LATEST=ROOT/'status/paper-portfolio-10k-analyst-latest.json'
INTEGRITY=ROOT/'status/paper-portfolio-10k-analyst-integrity.json'
SCHEMA='ATLAS_PAPER_10K_ANALYST_OUTPUT_V1'
CHECKPOINTS=(4,8,12)


def canon(x:Any)->str:return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def sha(x:Any)->str:return hashlib.sha256(canon(x).encode()).hexdigest()
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None
def parse(v):
    x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00')); return x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)
def jsonl(p):
    if not p.exists():return []
    out=[]
    for ln in p.read_text().splitlines():
        if ln.strip():out.append(json.loads(ln))
    return out

def load_manifest():
    m=json.loads(MANIFEST.read_text()); expected=m.get('manifest_hash'); body=dict(m); body.pop('manifest_hash',None)
    if sha(body)!=expected:raise RuntimeError('MANIFEST_LOCK_MISMATCH')
    if m.get('canonical_contract')!='analyst_output' or m.get('paper_only') is not True or m.get('live_execution') is not False:raise RuntimeError('SAFETY_CONTRACT_BROKEN')
    return m

def geometry(d):
    a=(d or {}).get('analyst_output') or {}
    direction=str(a.get('decision') or '').upper(); entry=num(a.get('entry')); stop=num(a.get('stop_loss')); tp=num(a.get('take_profit')); rr=num(a.get('risk_reward'))
    if direction not in {'LONG','SHORT'} or a.get('analysis_ready') is not True or None in (entry,stop,tp):return None
    risk=abs(entry-stop)
    if risk<=0:return None
    if direction=='LONG' and not(stop<entry<tp):return None
    if direction=='SHORT' and not(stop>entry>tp):return None
    rr=rr or abs(tp-entry)/risk
    tp1=entry+risk if direction=='LONG' else entry-risk
    return {'direction':direction,'entry':entry,'stop_loss':stop,'tp1':tp1,'tp2':tp,'rr_tp2':rr,'risk_abs':risk,'product_horizon':'4-12H','canonical_lane':'CORE_4_12H','contract_version':a.get('contract_version')}

def eligible(d):
    a=(d or {}).get('analyst_output') or {}; g=geometry(d)
    return bool(g and a.get('analysis_only') is True and a.get('live_execution') is False and str(a.get('decision') or '').upper() in {'LONG','SHORT'})

def snapshots(start):
    out=[]
    for r in jsonl(HISTORY):
        try:t=parse(r['captured_at'])
        except Exception:continue
        if t>=start:out.append((t,r))
    return sorted(out,key=lambda x:x[0])

def event_id(symbol,t,g):return hashlib.sha256(f"{symbol}|{t}|{g['direction']}|{g['entry']:.12g}|{g['stop_loss']:.12g}|{g['tp2']:.12g}".encode()).hexdigest()[:24]
def verify_append_only(rows,prev):
    h=[sha(r) for r in rows]; old=(prev or {}).get('row_hashes') or []
    if len(h)<len(old) or h[:len(old)]!=old:raise RuntimeError('COHORT_APPEND_ONLY_VIOLATION')
    return h

def enroll(m,cohort,rows,cursor,equity):
    ids={r['id'] for r in cohort}; state={}; added=[]; newest=cursor; horizon=dt.timedelta(hours=12); risk_pct=float(m['risk_per_trade_pct'])/100
    for t,s in rows:
        if t>cursor:break
        for sym,d in (s.get('decisions') or {}).items():state[sym]=geometry(d)['direction'] if eligible(d) else None
    for t,s in rows:
        if t<=cursor:continue
        newest=max(newest,t)
        for sym,d in (s.get('decisions') or {}).items():
            g=geometry(d) if eligible(d) else None; direction=g['direction'] if g else None; prior=state.get(sym); state[sym]=direction
            if not g or prior==direction:continue
            eid=event_id(sym,t.isoformat(),g)
            if eid in ids:continue
            openish=[r for r in cohort if parse(r['captured_at'])<=t<parse(r['captured_at'])+horizon]
            if len(openish)>=int(m['max_concurrent_positions']):continue
            a=d['analyst_output']; risk_usd=round(equity*risk_pct,2); qty=risk_usd/g['risk_abs']
            row={'schema':'ATLAS_PAPER_10K_ANALYST_ENTRY_V1','id':eid,'portfolio_id':m['portfolio_id'],'captured_at':t.isoformat(),'captured_at_ms':int(t.timestamp()*1000),'symbol':sym,'direction':direction,'decision_source':'COMMITTED_PRODUCTION_SNAPSHOT','decision_action':'ANALYST_OUTPUT_'+direction,'contract_version':a.get('contract_version'),'quality_gate_status':((a.get('setup_quality_gate') or {}).get('status')),'score':num(a.get('confidence')),'threshold':num(a.get('signal_threshold')),'geometry':g,'sizing_equity_usd':round(equity,2),'risk_pct':float(m['risk_per_trade_pct']),'risk_usd':risk_usd,'paper_quantity':round(qty,12),'paper_notional_usd':round(abs(qty*g['entry']),2),'evaluation_horizons':['4h','8h','12h'],'outcome_known_at_entry':False,'paper_only':True,'live_execution':False,'can_override_production':False,'manifest_hash':m['manifest_hash']}
            cohort.append(row); added.append(row); ids.add(eid)
    return added,newest

def checkpoint(row,h,now_ms):
    start=int(row['captured_at_ms']); end=start+h*3600_000; g=row['geometry']
    if now_ms<end:return {'checkpoint_h':h,'matured':False,'status':'NOT_MATURED','r_multiple':None}
    try:
        candles,provider=market_klines(row['symbol'],'5',start,end)
        if not candles:raise RuntimeError('no_5m_candles')
        ev,c,tp1=event_from(candles,g)
        if ev=='AMBIGUOUS' and c:
            one,p1=market_klines(row['symbol'],'1',c['open_time'],c['open_time']+5*60_000-1); ev1,c1,tp11=event_from(one,g); tp1=tp1 or tp11
            if ev1 in {'SL','TP2'}:ev,c=ev1,c1 or c
            provider+='+1M:'+p1
        if ev=='SL':status,r='LOSS_BY_CHECKPOINT',-1.0
        elif ev=='TP2':status,r='TP_BY_CHECKPOINT',float(g['rr_tp2'])
        elif ev=='AMBIGUOUS':status,r='AMBIGUOUS',None
        else:
            last=candles[-1]['close']; directional=(last-g['entry']) if g['direction']=='LONG' else (g['entry']-last); r=directional/g['risk_abs']; status='MARK_TO_MARKET'
        return {'checkpoint_h':h,'matured':True,'status':status,'r_multiple':None if r is None else round(float(r),4),'tp1_reached':bool(tp1),'market_source':provider}
    except Exception as e:return {'checkpoint_h':h,'matured':True,'status':'MARKET_DATA_ERROR','r_multiple':None,'error':str(e)[:500]}
def settle(row,now_ms):
    start=int(row['captured_at_ms']); end=start+12*3600_000; g=row['geometry']
    if now_ms<end:return {'status':'OPEN','terminal':False,'r_multiple':None,'exit_at_ms':None}
    try:
        candles,provider=market_klines(row['symbol'],'5',start,end)
        if not candles:raise RuntimeError('no_5m_candles')
        ev,c,tp1=event_from(candles,g)
        if ev=='AMBIGUOUS' and c:
            one,p1=market_klines(row['symbol'],'1',c['open_time'],c['open_time']+5*60_000-1); ev1,c1,tp11=event_from(one,g); tp1=tp1 or tp11
            if ev1 in {'SL','TP2'}:ev,c=ev1,c1 or c
            provider+='+1M:'+p1
        mfe,mae=excursions(candles,g)
        if ev=='SL':status,r,terminal,exit_ms='LOSS',-1.0,True,int(c['open_time'] if c else end)
        elif ev=='TP2':status,r,terminal,exit_ms='WIN_TP',float(g['rr_tp2']),True,int(c['open_time'] if c else end)
        elif ev=='AMBIGUOUS':status,r,terminal,exit_ms='AMBIGUOUS',None,False,None
        else:
            last=candles[-1]['close']; directional=(last-g['entry']) if g['direction']=='LONG' else (g['entry']-last); r=directional/g['risk_abs']; status='EXPIRED_TP1' if tp1 else 'EXPIRED'; terminal=True; exit_ms=end
        return {'status':status,'terminal':terminal,'r_multiple':None if r is None else round(float(r),4),'exit_at_ms':exit_ms,'tp1_reached':bool(tp1),'mfe_r':mfe,'mae_r':mae,'market_source':provider}
    except Exception as e:return {'status':'MARKET_DATA_ERROR','terminal':False,'r_multiple':None,'exit_at_ms':None,'error':str(e)[:500]}
def report(m,cohort,settlements,cps,observed):
    start=float(m['starting_equity_usd']); equity=start; peak=start; maxdd=0; detail=[]; rs=[]; wins=losses=0
    closed=[]
    for row,s in zip(cohort,settlements):
        r=num(s.get('r_multiple'))
        if s.get('terminal') and r is not None:closed.append((s.get('exit_at_ms') or 10**30,row,s,r))
    closed.sort(key=lambda x:x[0]); eqmap={}
    for _,row,s,r in closed:
        pnl=round(float(row['risk_usd'])*r,2); equity=round(equity+pnl,2); peak=max(peak,equity); dd=(peak-equity)/peak*100 if peak else 0; maxdd=max(maxdd,dd); rs.append(r); wins+=pnl>0; losses+=pnl<0; eqmap[row['id']]={'pnl_usd':pnl,'equity_after_usd':equity,'drawdown_after_pct':round(dd,4)}
    for row,s in zip(cohort,settlements):detail.append({**row,'product_window_checkpoints':cps[row['id']],'settlement':s,**eqmap.get(row['id'],{'pnl_usd':None,'equity_after_usd':None,'drawdown_after_pct':None})})
    summary={}
    for h in CHECKPOINTS:
        vals=[num(cp.get('r_multiple')) for arr in cps.values() for cp in arr if cp.get('checkpoint_h')==h and cp.get('matured')]; vals=[x for x in vals if x is not None]; summary[f'{h}h']={'matured':len(vals),'avg_r':round(sum(vals)/len(vals),4) if vals else None,'positive_pct':round(100*sum(x>0 for x in vals)/len(vals),2) if vals else None}
    return {'schema':SCHEMA,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'observed_through_at':observed.isoformat(),'canonical_contract':'analyst_output','product_horizon':'4-12H','evaluation_horizons':['4h','8h','12h'],'paper_only':True,'live_execution':False,'can_override_production':False,'production_threshold_unchanged':m['production_threshold'],'methodology':'Prospective canonical analyst_output LONG/SHORT transitions only; frozen Entry/SL/TP; 4h/8h/12h checkpoints; 12h terminal evaluation.','checkpoint_summary':summary,'portfolio':{'starting_equity_usd':start,'equity_usd':round(equity,2),'net_pnl_usd':round(equity-start,2),'return_pct':round((equity/start-1)*100,4),'entries':len(cohort),'closed':len(closed),'open_or_unresolved':len(cohort)-len(closed),'wins':wins,'losses':losses,'win_rate_pct':round(100*wins/len(closed),2) if closed else None,'net_r':round(sum(rs),4),'avg_r':round(sum(rs)/len(rs),4) if rs else None,'max_drawdown_pct':round(maxdd,4)},'trades':detail}
def main():
    m=load_manifest(); start=parse(m['cohort_start_at']); rows=snapshots(start); cohort=jsonl(COHORT); prev_i=json.loads(INTEGRITY.read_text()) if INTEGRITY.exists() else None; prev=json.loads(LATEST.read_text()) if LATEST.exists() else None; verify_append_only(cohort,prev_i)
    cursor=parse(prev['observed_through_at']) if prev and prev.get('observed_through_at') else start-dt.timedelta(microseconds=1); equity=num((prev or {}).get('portfolio',{}).get('equity_usd')) or float(m['starting_equity_usd']); added,newest=enroll(m,cohort,rows,cursor,equity); now=int(time.time()*1000); settlements=[]; cps={}
    for i,row in enumerate(cohort):cps[row['id']]=[checkpoint(row,h,now) for h in CHECKPOINTS]; settlements.append(settle(row,now)); time.sleep(.1 if i and i%12==0 else 0)
    rep=report(m,cohort,settlements,cps,newest); COHORT.parent.mkdir(parents=True,exist_ok=True); COHORT.write_text('\n'.join(canon(r) for r in cohort)+('\n' if cohort else '')); LATEST.write_text(json.dumps(rep,indent=2,sort_keys=True)); hashes=verify_append_only(cohort,prev_i); integ={'schema':'ATLAS_PAPER_10K_ANALYST_INTEGRITY_V1','generated_at':rep['generated_at'],'manifest_hash':m['manifest_hash'],'append_only_verified':True,'row_count':len(cohort),'new_row_count':len(added),'row_hashes':hashes,'chain_sha256':hashlib.sha256(''.join(hashes).encode()).hexdigest(),'paper_only':True,'live_execution':False,'can_override_production':False}; INTEGRITY.write_text(json.dumps(integ,indent=2,sort_keys=True)); print(json.dumps({'added':len(added),'portfolio':rep['portfolio'],'checkpoint_summary':rep['checkpoint_summary']},indent=2))
if __name__=='__main__':main()
