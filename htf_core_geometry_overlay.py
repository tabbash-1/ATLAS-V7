"""Canonical 4-12H structural geometry for ATLAS.

Uses only aligned HTF product direction plus 4H/12H price-action levels. It never
changes Production score or threshold and never relabels geometry from an
opposite 1H/scorer direction. When HTF direction and entry confirmation disagree,
geometry is withheld and the product remains WAIT.

A legacy WAIT may be cleared only when the raw Production score was already
qualified and the sole blocker came from the superseded short-horizon geometry.
Consensus, threshold, data-health, reliability and quality vetoes are never
cleared here.
"""
from __future__ import annotations

VERSION = 'HTF_CORE_GEOMETRY_V2_LEGACY_WAIT_CLEARANCE'
PRODUCT_HORIZON = '4-12H'
MIN_RR = 1.0
LEGACY_GEOMETRY_ONLY_BLOCKERS = frozenset({
    'RR_BELOW_ONE_TO_ONE',
    'GEOMETRY_INCOMPLETE',
    'INVALID_ENTRY_SL_TP_ORDER',
})


def _f(v, default=None):
    try:
        return float(v)
    except Exception:
        return default


def _zone_price(zone, key='mid'):
    return _f((zone or {}).get(key)) if isinstance(zone, dict) else None


def _rr(entry, stop, target):
    if None in (entry, stop, target): return None
    risk=abs(entry-stop); reward=abs(target-entry)
    return reward/risk if risk>0 else None


def _candidate_levels(pa4, pa12, direction, entry):
    items=[]
    zone_key='nearest_resistance_zone' if direction=='LONG' else 'nearest_support_zone'
    for tf, frame in (('4h',pa4),('12h',pa12)):
        zone=(frame or {}).get(zone_key) or {}
        price=_zone_price(zone,'mid')
        if price is None: continue
        valid=(price>entry) if direction=='LONG' else (price<entry)
        if valid:
            items.append({'timeframe':tf,'price':price,'zone':zone})
    items.sort(key=lambda x:x['price'], reverse=(direction=='SHORT'))
    return items


def build(row):
    thesis=dict(row.get('htf_thesis') or {})
    pa=dict(row.get('htf_price_action') or {})
    frames=pa.get('frames') or {}
    pa4=frames.get('4h') or {}; pa12=frames.get('12h') or {}
    direction=row.get('product_direction') or thesis.get('product_direction') or thesis.get('direction')
    entry_confirmation=row.get('entry_confirmation_direction') or thesis.get('entry_confirmation_direction') or row.get('candidate_direction')
    alignment=row.get('direction_alignment') or thesis.get('direction_alignment')

    base={
        'version':VERSION,'product_horizon':PRODUCT_HORIZON,
        'product_direction':direction if direction in ('LONG','SHORT') else None,
        'entry_confirmation_direction':entry_confirmation if entry_confirmation in ('LONG','SHORT') else None,
        'direction_alignment':alignment,'score_changed':False,'threshold_changed':False,
        'min_rr':MIN_RR,'analysis_only':True,'live_execution':False,
    }
    if direction not in ('LONG','SHORT'):
        return {**base,'status':'WAIT','reason':'NO_HTF_PRODUCT_DIRECTION','ready':False}
    if entry_confirmation not in ('LONG','SHORT') or entry_confirmation!=direction or alignment=='OPPOSED':
        return {**base,'status':'WAIT','reason':'ENTRY_CONFIRMATION_NOT_ALIGNED_WITH_HTF','ready':False}
    if thesis.get('status')!='PASS':
        return {**base,'status':'WAIT','reason':thesis.get('reason') or 'HTF_THESIS_NOT_PASS','ready':False}
    if not pa4.get('ok') or not pa12.get('ok'):
        return {**base,'status':'WAIT','reason':'HTF_PRICE_ACTION_INCOMPLETE','ready':False}

    px=_f(pa4.get('price')) or _f(row.get('entry'))
    atr4=_f(pa4.get('atr14')); atr12=_f(pa12.get('atr14'))
    if px is None or atr4 is None or atr4<=0 or atr12 is None or atr12<=0:
        return {**base,'status':'WAIT','reason':'HTF_PRICE_OR_ATR_UNAVAILABLE','ready':False}

    selected=((row.get('htf_scenario_engine') or {}).get('selected_case') or {})
    trigger=_f(selected.get('trigger_level'))
    s=1 if direction=='LONG' else -1
    trigger_ahead = trigger is not None and ((direction=='LONG' and trigger>=px) or (direction=='SHORT' and trigger<=px))
    if trigger_ahead:
        entry=trigger+s*max(atr4*.05,abs(trigger)*.0004)
        entry_mode='HTF_BREAK_RETEST'
        entry_basis='4H_STRUCTURAL_TRIGGER_PLUS_BUFFER'
    else:
        entry=px
        entry_mode='HTF_ALIGNED_CURRENT_PRICE'
        entry_basis='ALIGNED_4H_12H_CURRENT_PRICE'

    stop_zone_key='nearest_support_zone' if direction=='LONG' else 'nearest_resistance_zone'
    stop_candidates=[]
    for tf, frame in (('4h',pa4),('12h',pa12)):
        zone=(frame or {}).get(stop_zone_key) or {}
        edge=_zone_price(zone,'low' if direction=='LONG' else 'high')
        if edge is None: continue
        valid=(edge<entry) if direction=='LONG' else (edge>entry)
        if valid: stop_candidates.append({'timeframe':tf,'price':edge,'zone':zone})
    if not stop_candidates:
        return {**base,'status':'WAIT','reason':'NO_HTF_STRUCTURAL_INVALIDATION','ready':False,'entry':round(entry,10)}
    stop_ref=max(stop_candidates,key=lambda x:x['price']) if direction=='LONG' else min(stop_candidates,key=lambda x:x['price'])
    stop=stop_ref['price']-atr4*.15 if direction=='LONG' else stop_ref['price']+atr4*.15
    risk=abs(entry-stop)
    if risk<=0:
        return {**base,'status':'WAIT','reason':'INVALID_HTF_RISK','ready':False}

    targets=_candidate_levels(pa4,pa12,direction,entry)
    if not targets:
        return {**base,'status':'WAIT','reason':'NO_HTF_STRUCTURAL_TARGET','ready':False,'entry':round(entry,10),'stop_loss':round(stop,10)}

    tp1=targets[0]['price']
    rr1=_rr(entry,stop,tp1)
    if rr1 is None or rr1<MIN_RR:
        return {
            **base,'status':'WAIT','reason':'INSUFFICIENT_HTF_ROOM_TO_TARGET','ready':False,
            'entry':round(entry,10),'stop_loss':round(stop,10),'tp1':round(tp1,10),
            'rr_tp1':round(rr1,3) if rr1 is not None else None,
            'target_source':{'timeframe':targets[0]['timeframe'],'zone':targets[0]['zone']},
        }

    if len(targets)>1 and abs(targets[1]['price']-tp1)>max(atr4*.25,entry*.001):
        tp2=targets[1]['price']; tp2_basis='SECOND_HTF_STRUCTURAL_ZONE'
    else:
        tp2=entry+s*max(risk*2.0,atr12*.8); tp2_basis='2R_OR_0_8_12H_ATR_EXTENSION'
    rr2=_rr(entry,stop,tp2)

    provenance={
        'geometry_version':VERSION,
        'direction_authority':'HTF_12H_4H',
        'entry_basis':entry_basis,
        'stop_basis':'NEAREST_4H_12H_STRUCTURAL_INVALIDATION_PLUS_0_15_4H_ATR',
        'tp1_basis':'NEAREST_4H_12H_STRUCTURAL_TARGET',
        'tp2_basis':tp2_basis,
        'stop_reference_timeframe':stop_ref['timeframe'],
        'stop_reference_zone':stop_ref['zone'],
        'tp1_reference_timeframe':targets[0]['timeframe'],
        'tp1_reference_zone':targets[0]['zone'],
        'atr4h':round(atr4,10),'atr12h':round(atr12,10),
        'score_or_threshold_changed':False,
        'one_hour_geometry_relabelled':False,
    }
    return {
        **base,'status':'READY','reason':'HTF_DIRECTION_AND_GEOMETRY_ALIGNED','ready':True,
        'entry_mode':entry_mode,'entry':round(entry,10),'stop_loss':round(stop,10),
        'tp1':round(tp1,10),'tp2':round(tp2,10),'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),
        'geometry_provenance':provenance,
        'entry_trigger': selected.get('trigger_condition') or thesis.get('trigger'),
        'invalidation': selected.get('invalidation_condition') or '4H/12H structural invalidation is breached.',
    }


def _legacy_geometry_only_wait(row):
    if not bool(row.get('production_signal_qualified')):
        return False, None
    candidate=row.get('candidate_direction')
    product=row.get('product_direction') or ((row.get('htf_thesis') or {}).get('product_direction'))
    if candidate not in ('LONG','SHORT') or candidate!=product:
        return False, None
    legacy_gate=dict(row.get('geometry_gate') or {})
    reason=str(row.get('actionable_reason') or legacy_gate.get('reason') or '').strip().upper()
    if reason in LEGACY_GEOMETRY_ONLY_BLOCKERS:
        return True, reason
    return False, reason or None


def install(atlas):
    if getattr(atlas,'_HTF_CORE_GEOMETRY_INSTALLED',False):
        return getattr(atlas,'HTF_CORE_GEOMETRY_STATE',{'enabled':True,'version':VERSION})
    original=atlas.production_decision

    def wrapped(symbol):
        row=original(symbol)
        if not isinstance(row,dict) or not row.get('ok'): return row
        before_score=row.get('score'); before_threshold=row.get('signal_threshold')
        geom=build(row)
        row['htf_core_geometry']=geom
        row['htf_core_geometry_version']=VERSION
        row['htf_core_geometry_score_preserved']=row.get('score')==before_score
        row['htf_core_geometry_threshold_preserved']=row.get('signal_threshold')==before_threshold
        matrix=dict(row.get('timeframe_matrix') or {}); matrix['htf_core_geometry']=geom; row['timeframe_matrix']=matrix

        plan=dict(row.get('trade_plan') or {})
        plan['legacy_entry_geometry']={
            'direction':plan.get('direction'),'entry':plan.get('entry'),'stop_loss':plan.get('stop_loss'),
            'tp1':plan.get('tp1'),'tp2':plan.get('tp2'),'geometry_provenance':plan.get('geometry_provenance'),
            'geometry_gate':dict(row.get('geometry_gate') or {}),
        }
        plan['htf_core_geometry']=geom
        if geom.get('ready'):
            plan.update({
                'direction':geom.get('product_direction'),'entry_mode':geom.get('entry_mode'),
                'entry':geom.get('entry'),'stop_loss':geom.get('stop_loss'),'tp1':geom.get('tp1'),'tp2':geom.get('tp2'),
                'rr_tp1':geom.get('rr_tp1'),'rr_tp2':geom.get('rr_tp2'),'entry_trigger':geom.get('entry_trigger'),
                'invalidation':geom.get('invalidation'),'geometry_provenance':geom.get('geometry_provenance'),
                'geometry_authority':'HTF_4H_12H',
            })
            row['entry']=geom.get('entry'); row['stop_loss']=geom.get('stop_loss'); row['take_profit']=geom.get('tp2'); row['risk_reward']=geom.get('rr_tp2')
            can_clear, legacy_reason=_legacy_geometry_only_wait(row)
            if can_clear:
                row['pre_htf_geometry_actionable_decision']=row.get('actionable_decision')
                row['pre_htf_geometry_actionable_reason']=row.get('actionable_reason')
                row['legacy_geometry_blocker_cleared']=legacy_reason
                row['actionable_decision']=geom.get('product_direction')
                row['actionable_reason']='HTF_4_12H_GEOMETRY_READY_RAW_SCORE_QUALIFIED'
                row['analysis_ready']=True
                row['setup_ready']=True
                row['opportunity_state']='ACTIONABLE'
                row['opportunity_state_reason']='RAW_SCORE_QUALIFIED_HTF_DIRECTION_AND_GEOMETRY_READY'
                # Execution routing remains disabled; this is an analysis signal promotion only.
                row['execution_ready']=False
                row['htf_analysis_promotion_only']=True
        elif row.get('actionable_decision') in ('LONG','SHORT'):
            row['pre_htf_geometry_actionable_decision']=row.get('actionable_decision')
            row['pre_htf_geometry_actionable_reason']=row.get('actionable_reason')
            row['actionable_decision']='WAIT'; row['actionable_reason']=geom.get('reason') or 'HTF_GEOMETRY_NOT_READY'
            row['analysis_ready']=False; row['setup_ready']=False; row['opportunity_state']='WATCH'
        row['trade_plan']=plan
        return row

    atlas.production_decision=wrapped
    atlas._HTF_CORE_GEOMETRY_INSTALLED=True
    atlas.HTF_CORE_GEOMETRY_STATE={
        'enabled':True,'version':VERSION,'product_horizon':PRODUCT_HORIZON,'min_rr':MIN_RR,
        'requires_direction_alignment':True,'uses_timeframes':['4h','12h'],
        'legacy_geometry_only_wait_clearance':sorted(LEGACY_GEOMETRY_ONLY_BLOCKERS),
        'can_clear_consensus_wait':False,'can_clear_threshold_wait':False,'can_clear_data_wait':False,
        'score_threshold_unchanged':True,'analysis_only':True,'live_execution':False,
    }
    return atlas.HTF_CORE_GEOMETRY_STATE
