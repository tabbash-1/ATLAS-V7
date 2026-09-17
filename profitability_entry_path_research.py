#!/usr/bin/env python3
"""ATLAS ENTRY-stage path diagnostics.
Uses fixed R-unit diagnostics, not fitted thresholds. MFE/MAE lack event ordering,
so this module never claims a counterfactual better entry/stop/target.
"""
from __future__ import annotations
import json, math, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'status/analyst-forward-attribution-latest.json'
OUT=ROOT/'status/profitability-entry-path-latest.json'

def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def parse_ts(v):
    try:
        d=datetime.fromisoformat(str(v).replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:return datetime.min.replace(tzinfo=timezone.utc)

def row(e):
    s=e.get('settlement') or {}; c=e.get('context') or {}; r=num(s.get('r_multiple')); mfe=num(s.get('mfe_r')); mae=num(s.get('mae_r'))
    if not s.get('terminal') or r is None:return None
    return {'captured_at':e.get('captured_at') or '', 'symbol':e.get('symbol'),'direction':e.get('direction'),'regime':c.get('regime'),'playbook':c.get('playbook'),
            'score_bucket':c.get('score_bucket'),'relative_strength_reason':c.get('relative_strength_reason'),'obstacle_reason':c.get('obstacle_reason'),
            'extension_guard_reason':c.get('extension_guard_reason'),'futures_reason':c.get('futures_reason'),'r':r,'mfe':mfe,'mae':mae}

def stats(rows):
    n=len(rows); path=[x for x in rows if x['mfe'] is not None and x['mae'] is not None]
    def pct(fn):return round(100*sum(1 for x in path if fn(x))/len(path),2) if path else None
    rs=[x['r'] for x in rows]
    return {'n':n,'path_n':len(path),'avg_r':round(sum(rs)/n,4) if n else None,
            'avg_mfe_r':round(sum(x['mfe'] for x in path)/len(path),4) if path else None,
            'avg_mae_r':round(sum(x['mae'] for x in path)/len(path),4) if path else None,
            'mfe_ge_0_5r_pct':pct(lambda x:x['mfe']>=.5),'mfe_ge_1r_pct':pct(lambda x:x['mfe']>=1),'mfe_ge_2r_pct':pct(lambda x:x['mfe']>=2),
            'mae_le_0_5r_pct':pct(lambda x:x['mae']<=.5),'mae_le_1r_pct':pct(lambda x:x['mae']<=1),
            'low_favorable_high_adverse_pct':pct(lambda x:x['mfe']<.5 and x['mae']>=1),
            'large_favorable_nonpositive_outcome_pct':pct(lambda x:x['mfe']>=2 and x['r']<=0)}

def grouped(rows,key):
    vals={}
    for x in rows:
        k=str(x.get(key) or 'UNKNOWN'); vals.setdefault(k,[]).append(x)
    return {k:stats(v) for k,v in sorted(vals.items())}

def build():
    src=json.loads(SRC.read_text()); rows=[r for r in (row(e) for e in src.get('entries') or []) if r]; rows.sort(key=lambda x:parse_ts(x['captured_at']))
    cut=int(len(rows)*.625); d,h=rows[:cut],rows[cut:]
    dimensions=['regime','playbook','score_bucket','relative_strength_reason','obstacle_reason','extension_guard_reason','futures_reason']
    return {'schema':'ATLAS_PROFITABILITY_ENTRY_PATH_RESEARCH_V1','stage':'ENTRY_RESEARCH','horizon':'4-12H','fixed_r_unit_thresholds':[0.5,1.0,2.0],
            'all_terminal':stats(rows),'chronological_discovery':stats(d),'chronological_holdout':stats(h),
            'discovery_breakdowns':{k:grouped(d,k) for k in dimensions},'holdout_breakdowns':{k:grouped(h,k) for k in dimensions},
            'interpretation':{'low_favorable_high_adverse':'MFE <0.5R and MAE >=1R flags poor path quality, not proof that entry timing caused the loss.',
                              'large_favorable_nonpositive_outcome':'MFE >=2R with realized R <=0 flags possible exit/path-sequence investigation; MFE/MAE alone cannot reveal which occurred first.'},
            'counterfactual_entry_claim_authorized':False,'stop_target_change_authorized':False,'production_mutation_authorized':False,'automatic_promotion':False,
            'decision':'DIAGNOSTICS_ONLY_NEED_ORDERED_CANDLE_PATH_FOR_ENTRY_CHANGES'}

def main():
    x=build(); OUT.write_text(json.dumps(x,indent=2,sort_keys=True)); print(json.dumps(x,indent=2,sort_keys=True))
if __name__=='__main__':main()
