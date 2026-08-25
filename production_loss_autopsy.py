#!/usr/bin/env python3
"""ATLAS Production loss autopsy + entry-quality diagnostics.

Read-only research module. It never changes Production score, threshold,
direction, geometry, or execution eligibility.
"""
from __future__ import annotations
import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path

SCHEMA='ATLAS_PRODUCTION_LOSS_AUTOPSY_V1'


def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None


def _mean(xs):
    xs=[x for x in xs if x is not None]
    return round(sum(xs)/len(xs),4) if xs else None


def classify_loss(r):
    if r.get('path_outcome')!='LOSS': return None
    if r.get('tp1_reached'): return 'POST_TP1_REVERSAL'
    g=r.get('geometry') or {}
    rr=_f(g.get('rr_tp2'))
    entry=_f(r.get('entry')); stop=_f(g.get('stop_loss'))
    stop_pct=(100*abs(entry-stop)/entry) if entry and stop else None
    if stop_pct is not None and stop_pct < 0.35: return 'STOP_TOO_TIGHT_CANDIDATE'
    if rr is not None and rr < 1: return 'INVALID_LEGACY_RR'
    return 'PRE_TP1_DIRECTION_OR_ENTRY_FAILURE'


def build_report(rows):
    rows=list(rows or [])
    terminal=[r for r in rows if r.get('terminal') and r.get('path_outcome') not in ('AMBIGUOUS','MARKET_DATA_ERROR')]
    wins=[r for r in terminal if _f(r.get('r_multiple')) is not None and _f(r.get('r_multiple'))>0]
    losses=[r for r in terminal if _f(r.get('r_multiple')) is not None and _f(r.get('r_multiple'))<0]
    causes=defaultdict(list)
    for r in losses: causes[classify_loss(r)].append(r)
    by_symbol={}
    for sym in sorted({str(r.get('symbol')) for r in terminal if r.get('symbol')}):
        sr=[r for r in terminal if str(r.get('symbol'))==sym]
        rs=[_f(r.get('r_multiple')) for r in sr]; rs=[x for x in rs if x is not None]
        by_symbol[sym]={'n':len(sr),'positive':sum(x>0 for x in rs),'negative':sum(x<0 for x in rs),'net_r':round(sum(rs),4) if rs else None}
    loss_rows=[]
    for r in losses:
        g=r.get('geometry') or {}; entry=_f(r.get('entry')); stop=_f(g.get('stop_loss'))
        loss_rows.append({'id':r.get('id'),'symbol':r.get('symbol'),'direction':r.get('direction'),'score':_f(r.get('score')),'cause':classify_loss(r),'tp1_reached':bool(r.get('tp1_reached')),'rr_tp2':_f(g.get('rr_tp2')),'stop_distance_pct':round(100*abs(entry-stop)/entry,4) if entry and stop else None,'r_multiple':_f(r.get('r_multiple'))})
    return {'schema':SCHEMA,'terminal':len(terminal),'wins':len(wins),'losses':len(losses),'win_rate_pct':round(100*len(wins)/(len(wins)+len(losses)),2) if wins or losses else None,'net_r':round(sum(_f(r.get('r_multiple')) or 0 for r in terminal),4),'avg_win_score':_mean([_f(r.get('score')) for r in wins]),'avg_loss_score':_mean([_f(r.get('score')) for r in losses]),'loss_cause_counts':{k:len(v) for k,v in sorted(causes.items())},'losses_after_tp1':sum(bool(r.get('tp1_reached')) for r in losses),'by_symbol':by_symbol,'loss_rows':loss_rows,'production_threshold':68,'production_threshold_changed':False,'production_score_adjustment':0,'research_only':True}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',required=True); p.add_argument('--output',default='status/production-loss-autopsy.json'); a=p.parse_args()
    x=json.loads(Path(a.input).read_text()); rows=x.get('rows') if isinstance(x,dict) else x
    out=build_report(rows or []); Path(a.output).parent.mkdir(parents=True,exist_ok=True); Path(a.output).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,sort_keys=True))
if __name__=='__main__': main()
