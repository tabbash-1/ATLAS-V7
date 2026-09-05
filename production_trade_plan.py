"""ATLAS canonical 4-12H analysis plan.

Builds one canonical 4-12H analysis geometry from the verified Production
signal. Legacy quick (1-3H) and extended swing (12-24H) lanes remain attached as
context only so existing consumers do not break, but neither lane can replace
the canonical ATLAS product horizon. This module never routes orders.
"""

from swing_target_engine import build as build_swing_targets

VERSION = 'PRODUCTION_TRADE_PLAN_V5_ANALYSIS_GEOMETRY_PROVENANCE'
GEOMETRY_VERSION = 'ATLAS_GEOMETRY_V5_ATR_STRUCTURE_PROVENANCE'
PRODUCT_HORIZON = '4-12H'
PRODUCT_EVALUATION_HORIZONS = ['4h', '8h', '12h']


def _num(v):
    try: return float(v)
    except Exception: return None


def _rr(entry, stop, target):
    if None in (entry, stop, target): return None
    risk=abs(entry-stop); reward=abs(target-entry)
    return reward/risk if risk>0 else None


def _conditional_reference(geom, direction, px):
    """Return the structure that must be cleared before a conditional breakout."""
    br=(geom or {}).get('breakout') or {}
    obstacle=_num((geom or {}).get('obstacle_price'))
    high24=_num(br.get('prior_24h_high'))
    low24=_num(br.get('prior_24h_low'))

    if direction=='LONG':
        candidates=[]
        if obstacle is not None and obstacle>px: candidates.append((obstacle,'STRUCTURAL_OBSTACLE'))
        if high24 is not None and high24>px: candidates.append((high24,'PRIOR_24H_HIGH'))
        return max(candidates,key=lambda x:x[0]) if candidates else (None,None)

    candidates=[]
    if obstacle is not None and obstacle<px: candidates.append((obstacle,'STRUCTURAL_OBSTACLE'))
    if low24 is not None and low24<px: candidates.append((low24,'PRIOR_24H_LOW'))
    return min(candidates,key=lambda x:x[0]) if candidates else (None,None)


def build(decision):
    if not isinstance(decision,dict) or not decision.get('ok'):
        return {'status':'UNAVAILABLE','reason':'NO_VERIFIED_DECISION','version':VERSION,'geometry_version':GEOMETRY_VERSION,'product_horizon':PRODUCT_HORIZON,'analysis_only':True,'live_execution':False}
    d=decision.get('candidate_direction')
    if d not in ('LONG','SHORT'):
        return {'status':'WAIT','direction':None,'entry_mode':'NONE','reason':'NO_DIRECTIONAL_CONSENSUS','version':VERSION,'geometry_version':GEOMETRY_VERSION,'product_horizon':PRODUCT_HORIZON,'analysis_only':True,'live_execution':False}
    s=1 if d=='LONG' else -1
    px=_num(decision.get('entry')); atr=_num((decision.get('indicators') or {}).get('atr14'))
    geom=decision.get('structural_geometry') or {}; br=geom.get('breakout') or {}
    obstacle=_num(geom.get('obstacle_price'))
    continuation=bool(geom.get('continuation_strong')); breakout=bool(br.get('confirmed'))
    qualified=bool(decision.get('production_signal_qualified'))
    ready_raw=bool(decision.get('execution_ready'))  # legacy name; means geometry/current-entry readiness only.
    threshold=_num(decision.get('signal_threshold'))
    if threshold is None: threshold=68.0
    if px is None or atr is None or atr<=0:
        return {'status':'WAIT','direction':d,'entry_mode':'NONE','reason':'ATR_OR_PRICE_UNAVAILABLE','version':VERSION,'geometry_version':GEOMETRY_VERSION,'product_horizon':PRODUCT_HORIZON,'analysis_only':True,'live_execution':False}

    base_stop=px-s*atr*1.2
    entry=px; mode='NOW'; trigger='Canonical analysis is valid while the verified setup and structure remain intact.'
    reference=obstacle; reference_source='STRUCTURAL_OBSTACLE' if obstacle is not None else None
    stop_basis='CURRENT_PRICE_PLUS_1_2_ATR_INVALIDATION'
    entry_basis='VERIFIED_CURRENT_PRICE'

    if not ready_raw:
        blocker, blocker_source=_conditional_reference(geom,d,px)
        blocker_dist=None
        if blocker is not None and px:
            blocker_dist=((blocker/px)-1)*100 if d=='LONG' else ((px/blocker)-1)*100

        if blocker is not None and blocker_dist is not None and blocker_dist<=1.5:
            buffer=max(atr*.10,abs(blocker)*.0005)
            entry=blocker+s*buffer
            mode='BREAKOUT'
            trigger=('LONG analysis activates only after a verified 1H close/hold above ' if d=='LONG' else 'SHORT analysis activates only after a verified 1H close/hold below ')+f'{blocker:.8g}.'
            base_stop=entry-s*atr*.85
            reference=blocker; reference_source=blocker_source
            entry_basis='STRUCTURE_BREAK_PLUS_BUFFER'
            stop_basis='POST_BREAKOUT_ENTRY_PLUS_0_85_ATR_INVALIDATION'
        else:
            entry=px-s*atr*.35
            mode='PULLBACK'
            trigger='Analysis activates only if the pullback holds trend structure and verified directional evidence remains valid.'
            base_stop=entry-s*atr*.9
            entry_basis='ATR_PULLBACK_0_35'
            stop_basis='PULLBACK_ENTRY_PLUS_0_9_ATR_INVALIDATION'
            if blocker is not None:
                reference=blocker; reference_source=blocker_source

    stop=base_stop
    risk=abs(entry-stop)
    one_r=entry+s*risk
    structural_tp=obstacle if obstacle is not None and ((d=='LONG' and obstacle>one_r) or (d=='SHORT' and obstacle<one_r)) else None
    tp1=structural_tp if structural_tp is not None else one_r
    tp1_basis='PRIOR_STRUCTURAL_OBSTACLE' if structural_tp is not None else 'MINIMUM_1R'
    extension_mult=2.2 if continuation or breakout else 1.8
    tp2=entry+s*max(risk*2.0,atr*extension_mult)
    tp2_basis='MAX_2R_OR_2_2ATR' if continuation or breakout else 'MAX_2R_OR_1_8ATR'
    if d=='LONG' and tp2<=tp1:
        tp2=tp1+max(risk,atr*.8); tp2_basis+=' + ORDERING_GUARD'
    if d=='SHORT' and tp2>=tp1:
        tp2=tp1-max(risk,atr*.8); tp2_basis+=' + ORDERING_GUARD'
    rr1=_rr(entry,stop,tp1); rr2=_rr(entry,stop,tp2)
    risk_atr=(risk/atr) if atr>0 else None
    risk_pct=(risk/entry*100) if entry else None

    extended_swing=build_swing_targets(
        direction=d,
        entry=entry,
        stop=stop,
        atr=atr,
        structural_geometry=geom,
        continuation_strong=continuation,
        breakout_confirmed=breakout,
    )

    analysis_ready=bool(ready_raw and qualified)
    status='ACTIONABLE' if analysis_ready else 'CONDITIONAL'  # legacy compatibility status.
    action=('BUY' if d=='LONG' else 'SELL') if status=='ACTIONABLE' else ('BUY_ONLY_IF' if d=='LONG' else 'SELL_ONLY_IF')
    can_execute=analysis_ready  # compatibility only; live_execution remains false.
    analysis_action=d if analysis_ready else 'WAIT'
    provenance={
        'geometry_version':GEOMETRY_VERSION,
        'entry_basis':entry_basis,
        'stop_basis':stop_basis,
        'tp1_basis':tp1_basis,
        'tp2_basis':tp2_basis,
        'reference_structure':round(reference,10) if reference is not None else None,
        'reference_structure_source':reference_source,
        'atr14':round(atr,10),
        'risk_atr':round(risk_atr,4) if risk_atr is not None else None,
        'risk_pct':round(risk_pct,4) if risk_pct is not None else None,
        'breakout_confirmed':breakout,
        'continuation_strong':continuation,
        'score_or_threshold_changed':False,
    }

    core_plan={
        'lane':'CORE_4_12H','role':'PRIMARY_PRODUCT_LANE','horizon':PRODUCT_HORIZON,
        'evaluation_horizons':list(PRODUCT_EVALUATION_HORIZONS),'status':status,
        'action':action,'analysis_action':analysis_action,'analysis_ready':analysis_ready,
        'direction':d,'entry_mode':mode,'entry':round(entry,10),'entry_trigger':trigger,
        'stop_loss':round(stop,10),'tp1':round(tp1,10),'tp2':round(tp2,10),
        'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),'geometry_provenance':provenance,
        'can_execute':can_execute,'analysis_only':True,'live_execution':False,'research_only':True,
    }

    return {
        'version':VERSION,'geometry_version':GEOMETRY_VERSION,'status':status,'action':action,
        'analysis_action':analysis_action,'analysis_ready':analysis_ready,'direction':d,'entry_mode':mode,
        'product_horizon':PRODUCT_HORIZON,'evaluation_horizons':list(PRODUCT_EVALUATION_HORIZONS),
        'canonical_lane':'CORE_4_12H','entry':round(entry,10),'entry_trigger':trigger,
        'stop_loss':round(stop,10),'tp1':round(tp1,10),'tp2':round(tp2,10),
        'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),'geometry_provenance':provenance,
        'core_plan':core_plan,
        'quick_plan':{'role':'CONTEXT_ONLY','horizon':'1-3H','tp1':round(tp1,10),'tp2':round(tp2,10),'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),'can_override_core':False},
        'swing_plan':{**extended_swing,'role':'CONTEXT_ONLY','can_override_core':False},
        'preferred_target_lane':'CORE_4_12H','reference_structure':round(reference,10) if reference is not None else None,
        'reference_structure_source':reference_source,'continuation_strong':continuation,'breakout_confirmed':breakout,
        'qualification_required':threshold,'production_qualified':qualified,'execution_ready':ready_raw,
        'invalidation':'Re-evaluate if stop/structure fails or the verified direction changes.',
        'can_execute':can_execute,'execution_scope':'DECISION_READY_ONLY_NO_ORDER_ROUTING',
        'analysis_only':True,'live_execution':False,'research_only':True,
    }
