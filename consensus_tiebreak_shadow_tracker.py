#!/usr/bin/env python3
"""Settle prospective consensus tie-break shadow observations at 1h and 3h.

Input is a JSONL history where every snapshot contains current research endpoint
responses for the full symbol universe. A SHADOW_SIGNAL observation is settled
against the earliest later snapshot at/after the target horizon, provided the
sampling lag is <= 75 minutes. Production is never modified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

SCHEMA = "ATLAS_CONSENSUS_TIEBREAK_PROSPECTIVE_V1"
HORIZONS = (1, 3)
MAX_LAG_MINUTES = 75


def fnum(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def parse_time(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception:
        return None


def load_history(path):
    p=Path(path)
    if not p.exists():
        return []
    out=[]
    for line in p.read_text(errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            x=json.loads(line)
        except Exception:
            continue
        if isinstance(x,dict):
            out.append(x)
    return out


def directional_return(entry, future, direction):
    if not entry or not future or direction not in ('LONG','SHORT'):
        return None
    pct=(future/entry-1.0)*100.0
    return pct if direction=='LONG' else -pct


def candidate_episodes(snapshots):
    chosen={}
    for snap in snapshots:
        captured=parse_time(snap.get('captured_at'))
        if captured is None:
            continue
        for symbol, sig in (snap.get('signals') or {}).items():
            if not isinstance(sig,dict) or sig.get('status')!='SHADOW_SIGNAL':
                continue
            generated=parse_time(sig.get('generated_at')) or captured
            price=fnum(sig.get('reference_price'))
            direction=sig.get('direction')
            if generated is None or price is None or price<=0 or direction not in ('LONG','SHORT'):
                continue
            key=(symbol,generated.replace(minute=0,second=0,microsecond=0).isoformat())
            item={
                'symbol':symbol,'signal_at':generated,'entry':price,'direction':direction,
                'momentum_24h_pct':fnum(sig.get('momentum_24h_pct')),
                'source':sig.get('source'),'rule':sig.get('rule'),
            }
            prev=chosen.get(key)
            if prev is None or generated<prev['signal_at']:
                chosen[key]=item
    return sorted(chosen.values(),key=lambda x:x['signal_at'])


def future_price(snapshots,symbol,target):
    candidates=[]
    for snap in snapshots:
        captured=parse_time(snap.get('captured_at'))
        if captured is None or captured<target:
            continue
        sig=(snap.get('signals') or {}).get(symbol) or {}
        price=fnum(sig.get('reference_price'))
        if price is None or price<=0:
            continue
        lag=(captured-target).total_seconds()/60.0
        candidates.append((captured,lag,price))
    if not candidates:
        return None
    captured,lag,price=min(candidates,key=lambda x:x[0])
    if lag>MAX_LAG_MINUTES:
        return None
    return {'observed_at':captured.isoformat(),'lag_minutes':round(lag,2),'price':price}


def stats(rows):
    vals=[r['directional_return_pct'] for r in rows if r.get('directional_return_pct') is not None]
    if not vals:
        return {'n':0}
    return {
        'n':len(vals),
        'mean_directional_return_pct':round(mean(vals),4),
        'median_directional_return_pct':round(median(vals),4),
        'win_rate_pct':round(100*sum(v>0 for v in vals)/len(vals),2),
        'gain_ge_0_5_pct':sum(v>=0.5 for v in vals),
        'loss_le_minus_0_5_pct':sum(v<=-0.5 for v in vals),
        'best_pct':round(max(vals),4),
        'worst_pct':round(min(vals),4),
    }


def build_report(snapshots):
    episodes=candidate_episodes(snapshots)
    settled={1:[],3:[]}
    details=[]
    for ep in episodes:
        row={
            'symbol':ep['symbol'],'signal_at':ep['signal_at'].isoformat(),
            'entry':ep['entry'],'direction':ep['direction'],
            'momentum_24h_pct':ep['momentum_24h_pct'],'source':ep['source'],'rule':ep['rule'],
            'outcomes':{},
        }
        for h in HORIZONS:
            target=ep['signal_at']+dt.timedelta(hours=h)
            fp=future_price(snapshots,ep['symbol'],target)
            if fp:
                dr=directional_return(ep['entry'],fp['price'],ep['direction'])
                outcome={**fp,'directional_return_pct':round(dr,4)}
                settled[h].append({'symbol':ep['symbol'],'directional_return_pct':dr})
            else:
                outcome={'status':'PENDING_OR_SAMPLING_GAP'}
            row['outcomes'][f'{h}h']=outcome
        details.append(row)

    by_symbol={}
    symbols=sorted({e['symbol'] for e in episodes})
    for s in symbols:
        by_symbol[s]={f'{h}h':stats([x for x in settled[h] if x['symbol']==s]) for h in HORIZONS}

    n1=len(settled[1]); n3=len(settled[3]); n=min(n1,n3)
    if n<10:
        tier='HYPOTHESIS'
    elif n<30:
        tier='PRELIMINARY'
    else:
        tier='SERIOUS_CANDIDATE'

    first=min((e['signal_at'] for e in episodes),default=None)
    last=max((e['signal_at'] for e in episodes),default=None)
    return {
        'schema':SCHEMA,
        'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'rule':'EXACT_2_2_FOLLOW_24H_MOMENTUM_SIGN',
        'horizons_hours':[1,3],
        'prospective_only':True,
        'guardrails':{
            'research_only':True,'production_changed':False,'production_threshold':68,
            'auto_promotion':False,'can_override_production':False,'live_execution':False,
        },
        'coverage':{
            'snapshots':len(snapshots),'shadow_signal_episodes':len(episodes),
            'first_signal_at':first.isoformat() if first else None,
            'last_signal_at':last.isoformat() if last else None,
            'settled_1h':n1,'settled_3h':n3,
            'evidence_tier':tier,
        },
        'performance':{'1h':stats(settled[1]),'3h':stats(settled[3])},
        'by_symbol':by_symbol,
        'episodes':details[-100:],
        'decision_rule':'Prospective evidence is descriptive only. Never auto-promote; compare with the frozen historical audit before any Production proposal.',
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',default='status/history/consensus-tiebreak-shadow-snapshots.jsonl')
    ap.add_argument('--output',default='status/consensus-tiebreak-shadow-prospective.json')
    args=ap.parse_args()
    report=build_report(load_history(args.input))
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps({'schema':report['schema'],'coverage':report['coverage'],'performance':report['performance']},indent=2))


if __name__=='__main__':
    main()
