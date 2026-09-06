"""ATLAS HTF scenario outcome calibration.

Research-only evaluator for conditional 4-12H scenarios. It measures whether
scenario triggers occurred, whether invalidation occurred first, and forward
returns after activation. It never changes Production scoring, thresholds,
readiness, or execution.
"""

VERSION='SCENARIO_OUTCOME_CALIBRATION_V1'; HORIZONS=(4,8,12); MIN_DECISIVE_SAMPLE=20

def _f(v,default=None):
    try: return float(v) if v is not None else default
    except (TypeError,ValueError): return default

def _directional_return(direction,raw):
    v=_f(raw)
    if v is None: return None
    d=str(direction or '').upper(); return v if d=='LONG' else -v if d=='SHORT' else None

def _event_state(row):
    trigger=row.get('triggered') is True; invalidated=row.get('invalidated') is True; tt=row.get('triggered_at'); it=row.get('invalidated_at')
    if trigger and invalidated and tt and it: return 'INVALIDATED_BEFORE_TRIGGER' if str(it)<str(tt) else 'TRIGGERED_THEN_INVALIDATED'
    if trigger: return 'TRIGGERED'
    if invalidated: return 'INVALIDATED_BEFORE_TRIGGER'
    return 'UNRESOLVED'

def _stage(row):
    stage=str(row.get('scenario_stage') or '').upper()
    if stage in ('WATCH','ARMED'): return stage
    readiness=str(row.get('scenario_readiness') or '').upper()
    if readiness=='WATCH_SCENARIO': return 'WATCH'
    if readiness=='CONDITIONAL_SCENARIO_READY': return 'LEGACY_CONDITIONAL' if not row.get('readiness_classification_version') else 'ARMED'
    return 'LEGACY_OR_UNKNOWN'

def _stats(items,horizon):
    vals=[]
    for row in items:
        val=_directional_return(row.get('direction'),(row.get('forward_return_pct') or {}).get(str(horizon)))
        if val is not None: vals.append(val)
    wins=[v for v in vals if v>0]; losses=[v for v in vals if v<0]; decisive=len(wins)+len(losses)
    return {'total':len(items),'matured':len(vals),'wins':len(wins),'losses':len(losses),'win_rate_pct':round(100*len(wins)/decisive,2) if decisive else None,'avg_directional_return_pct':round(sum(vals)/len(vals),6) if vals else None,'sample_sufficient':decisive>=MIN_DECISIVE_SAMPLE}

def calibrate(rows,horizon=12):
    horizon=int(horizon)
    if horizon not in HORIZONS: raise ValueError('horizon must be one of 4, 8, 12')
    obs=[]
    for row in rows or []:
        direction=str(row.get('direction') or '').upper()
        if direction not in ('LONG','SHORT'): continue
        obs.append({**row,'direction':direction,'event_state':_event_state(row),'calibration_stage':_stage(row)})
    by_state={}; by_trigger={}; by_symbol={}; by_stage={}
    for row in obs:
        by_state.setdefault(row['event_state'],[]).append(row); by_trigger.setdefault(str(row.get('trigger_type') or 'UNKNOWN'),[]).append(row); by_symbol.setdefault(str(row.get('symbol') or 'UNKNOWN'),[]).append(row); by_stage.setdefault(row['calibration_stage'],[]).append(row)
    triggered=[r for r in obs if r['event_state'] in ('TRIGGERED','TRIGGERED_THEN_INVALIDATED')]; invalidated_first=[r for r in obs if r['event_state']=='INVALIDATED_BEFORE_TRIGGER']; unresolved=[r for r in obs if r['event_state']=='UNRESOLVED']
    return {'schema':'ATLAS_SCENARIO_OUTCOME_CALIBRATION_V1','version':VERSION,'horizon_h':horizon,'observations':len(obs),'triggered':len(triggered),'invalidated_before_trigger':len(invalidated_first),'unresolved':len(unresolved),'overall_triggered':_stats(triggered,horizon),'by_event_state':{k:_stats(v,horizon) for k,v in sorted(by_state.items())},'by_trigger_type':{k:_stats(v,horizon) for k,v in sorted(by_trigger.items())},'by_symbol':{k:_stats(v,horizon) for k,v in sorted(by_symbol.items())},'by_scenario_stage':{k:_stats(v,horizon) for k,v in sorted(by_stage.items())},'recommendation':{'status':'EVIDENCE_COLLECTION','minimum_decisive_sample':MIN_DECISIVE_SAMPLE,'auto_apply':False},'methodology':'Conditional HTF scenarios grouped by frozen WATCH/ARMED stage, trigger occurrence, invalidation order, and directional forward return. Legacy observations remain separately labeled.','research_only':True,'live_execution':False,'score_changed':False,'threshold_changed':False,'readiness_changed':False,'production_decision_changed':False}
