#!/usr/bin/env python3
"""De-correlate ATLAS Swing calibration into independent 12h episodes.

Hourly/repeated snapshots of the same symbol/direction/obstacle are not treated as
independent evidence. For each combo, a new calibration episode can start only
12 hours after the previously accepted episode start. This is research-only.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCHEMA='ATLAS_SWING_EPISODE_CALIBRATION_V1'
EPISODE_GAP_HOURS=12
MIN_EPISODES_FOR_DIRECTIONAL_TIER=5


def _dt(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except ValueError:return None


def _f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None


def combo(row):
    s=str(row.get('symbol') or 'UNKNOWN').upper()
    d=str(row.get('candidate_direction') or 'NONE').upper()
    o=str(((row.get('score_attribution') or {}).get('obstacle_reason') or 'NONE')).upper()
    return f'{s}|{d}|{o}'


def de_correlate(rows,gap_hours=EPISODE_GAP_HOURS):
    grouped=defaultdict(list)
    for r in rows:
        t=_dt(r.get('wait_at'))
        d=str(r.get('candidate_direction') or 'NONE').upper()
        if t is None or d not in ('LONG','SHORT'):continue
        grouped[combo(r)].append((t,r))
    accepted=[]
    gap=timedelta(hours=gap_hours)
    for key,items in grouped.items():
        items.sort(key=lambda x:x[0])
        last=None
        for t,r in items:
            if last is None or t-last>=gap:
                x=dict(r);x['_episode_combo']=key;x['_episode_start']=t.isoformat()
                accepted.append(x);last=t
    accepted.sort(key=lambda r:r['_episode_start'])
    return accepted


def summary(vals):
    vals=[x for x in (_f(v) for v in vals) if x is not None]
    if not vals:return {'n':0,'positive_rate_pct':None,'mean_pct':None,'median_pct':None}
    n=len(vals)
    return {'n':n,'positive_rate_pct':round(100*sum(v>0 for v in vals)/n,2),'mean_pct':round(sum(vals)/n,4),'median_pct':round(statistics.median(vals),4)}


def build_report(payload):
    rows=list((payload or {}).get('records') or [])
    episodes=de_correlate(rows)
    grouped=defaultdict(list)
    for e in episodes:grouped[e['_episode_combo']].append(e)
    combos={}
    for key,eps in sorted(grouped.items()):
        h12=summary(((e.get('horizons') or {}).get('12h') or {}).get('directional_return_pct') for e in eps)
        h24=summary(((e.get('horizons') or {}).get('24h') or {}).get('directional_return_pct') for e in eps)
        n=h12['n'];pos=h12['positive_rate_pct'];mean=h12['mean_pct']
        if n<MIN_EPISODES_FOR_DIRECTIONAL_TIER:verdict='INSUFFICIENT_INDEPENDENT_EPISODES'
        elif mean is not None and pos is not None and mean>0 and pos>=60:verdict='INDEPENDENT_POSITIVE_EDGE'
        elif mean is not None and mean<0:verdict='INDEPENDENT_NEGATIVE_EDGE'
        else:verdict='INDEPENDENT_NEUTRAL'
        combos[key]={'raw_episode_candidates':len(eps),'12h':h12,'24h':h24,'verdict':verdict,'production_change_allowed':False}
    raw_directional=sum(1 for r in rows if str(r.get('candidate_direction') or '').upper() in ('LONG','SHORT'))
    return {
        'schema':SCHEMA,'generated_at':datetime.now(timezone.utc).isoformat(),
        'methodology':f'First observation per {EPISODE_GAP_HOURS}h combo episode; repeated snapshots inside an episode are excluded from independent sample counts.',
        'episode_gap_hours':EPISODE_GAP_HOURS,
        'raw_directional_records':raw_directional,
        'independent_episode_records':len(episodes),
        'independence_ratio_pct':round(100*len(episodes)/raw_directional,2) if raw_directional else None,
        'minimum_episodes_for_tier':MIN_EPISODES_FOR_DIRECTIONAL_TIER,
        'combos':combos,
        'production_threshold':68,'production_threshold_changed':False,'production_score_adjustment':0,'auto_promotion_enabled':False,'research_only':True,
    }


def main():
    p=argparse.ArgumentParser();p.add_argument('--wait-outcomes',default='status/wait-outcomes.json');p.add_argument('--output',default='status/swing-episode-calibration.json');a=p.parse_args()
    report=build_report(json.loads(Path(a.wait_outcomes).read_text()))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'raw':report['raw_directional_records'],'episodes':report['independent_episode_records']},sort_keys=True))
if __name__=='__main__':main()
