"""ATLAS Production Trade Plan V3.

Builds a complete, auditable quick-trade plan from the verified decision and
also attaches a separate structure-aware 12-24H swing target lane. The legacy
Production TP1/TP2 geometry is preserved for compatibility; swing targets never
silently replace the quick-trade plan.
"""

from swing_target_engine import build as build_swing_targets

VERSION = 'PRODUCTION_TRADE_PLAN_V3_SWING_LANE'


def _num(v):
    try: return float(v)
    except Exception: return None


def _rr(entry, stop, target):
    if None in (entry, stop, target): return None
    risk=abs(entry-stop); reward=abs(target-entry)
    return reward/risk if risk>0 else None


def _conditional_reference(geom, direction, px):
    """Return the structure that must be cleared before a conditional breakout.

    The nearest swing remains useful evidence, but a trade is not genuinely
    through resistance/support if it is still trapped inside the prior 24h
    range. For LONG use the highest relevant blocker ahead; for SHORT use the
    lowest relevant blocker below. Levels behind price are ignored.
    """
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
        return {'status':'UNAVAILABLE','reason':'NO_VERIFIED_DECISION','version':VERSION}
    d=decision.get('candidate_direction')
    if d not in ('LONG','SHORT'):
        return {'status':'WAIT','direction':None,'entry_mode':'NONE','reason':'NO_DIRECTIONAL_CONSENSUS','version':VERSION}
    s=1 if d=='LONG' else -1
    px=_num(decision.get('entry')); atr=_num((decision.get('indicators') or {}).get('atr14'))
    geom=decision.get('structural_geometry') or {}; br=geom.get('breakout') or {}
    obstacle=_num(geom.get('obstacle_price'))
    continuation=bool(geom.get('continuation_strong')); breakout=bool(br.get('confirmed'))
    qualified=bool(decision.get('production_signal_qualified'))
    execution=bool(decision.get('execution_ready'))
    if px is None or atr is None or atr<=0:
        return {'status':'WAIT','direction':d,'entry_mode':'NONE','reason':'ATR_OR_PRICE_UNAVAILABLE','version':VERSION}

    base_stop=px-s*atr*1.2
    entry=px; mode='NOW'; trigger='Verified Production setup is executable now.'
    reference=obstacle; reference_source='STRUCTURAL_OBSTACLE' if obstacle is not None else None

    # If current Production geometry is not executable, choose a conditional
    # location. A breakout must clear BOTH the nearest swing and the prior 24h
    # range boundary when either is still ahead of price.
    if not execution:
        blocker, blocker_source=_conditional_reference(geom,d,px)
        blocker_dist=None
        if blocker is not None and px:
            blocker_dist=((blocker/px)-1)*100 if d=='LONG' else ((px/blocker)-1)*100

        if blocker is not None and blocker_dist is not None and blocker_dist<=1.5:
            buffer=max(atr*.10,abs(blocker)*.0005)
            entry=blocker+s*buffer
            mode='BREAKOUT'
            trigger=('Buy only after 1H close/hold above ' if d=='LONG' else 'Sell only after 1H close/hold below ')+f'{blocker:.8g}.'
            base_stop=entry-s*atr*.85
            reference=blocker; reference_source=blocker_source
        else:
            entry=px-s*atr*.35
            mode='PULLBACK'
            trigger='Enter only if the pullback holds trend structure and directional evidence remains valid.'
            base_stop=entry-s*atr*.9
            if blocker is not None:
                reference=blocker; reference_source=blocker_source

    stop=base_stop
    risk=abs(entry-stop)
    one_r=entry+s*risk
    structural_tp=obstacle if obstacle is not None and ((d=='LONG' and obstacle>one_r) or (d=='SHORT' and obstacle<one_r)) else None
    tp1=structural_tp if structural_tp is not None else one_r
    extension_mult=2.2 if continuation or breakout else 1.8
    tp2=entry+s*max(risk*2.0,atr*extension_mult)
    if d=='LONG' and tp2<=tp1: tp2=tp1+max(risk,atr*.8)
    if d=='SHORT' and tp2>=tp1: tp2=tp1-max(risk,atr*.8)
    rr1=_rr(entry,stop,tp1); rr2=_rr(entry,stop,tp2)

    swing_plan=build_swing_targets(
        direction=d,
        entry=entry,
        stop=stop,
        atr=atr,
        structural_geometry=geom,
        continuation_strong=continuation,
        breakout_confirmed=breakout,
    )

    status='ACTIONABLE' if execution and qualified else 'CONDITIONAL'
    action=('BUY' if d=='LONG' else 'SELL') if status=='ACTIONABLE' else ('BUY_ONLY_IF' if d=='LONG' else 'SELL_ONLY_IF')
    return {
        'version':VERSION,'status':status,'action':action,'direction':d,'entry_mode':mode,
        'entry':round(entry,10),'entry_trigger':trigger,'stop_loss':round(stop,10),
        'tp1':round(tp1,10),'tp2':round(tp2,10),'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),
        'quick_plan':{
            'horizon':'1-3H','tp1':round(tp1,10),'tp2':round(tp2,10),
            'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3)
        },
        'swing_plan':swing_plan,
        'preferred_target_lane':'SWING_12_24H' if swing_plan.get('status')=='SWING_READY' else 'QUICK_1_3H',
        'reference_structure':round(reference,10) if reference is not None else None,
        'reference_structure_source':reference_source,
        'continuation_strong':continuation,'breakout_confirmed':breakout,
        'qualification_required':68,'production_qualified':qualified,'execution_ready':execution,
        'invalidation':'Cancel/re-evaluate if stop/structure fails or verified direction changes.',
        'can_execute':False,'research_only':True,
    }
