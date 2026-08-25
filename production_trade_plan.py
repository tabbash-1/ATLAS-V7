"""ATLAS Production Trade Plan V1.

Builds a complete, auditable plan from the verified decision: entry mode,
entry trigger, structural/ATR stop, TP1/TP2 and risk/reward. It does not lower
qualification thresholds and does not execute trades.
"""

VERSION = 'PRODUCTION_TRADE_PLAN_V1'


def _num(v):
    try: return float(v)
    except Exception: return None


def _rr(entry, stop, target):
    if None in (entry, stop, target): return None
    risk=abs(entry-stop); reward=abs(target-entry)
    return reward/risk if risk>0 else None


def build(decision):
    if not isinstance(decision,dict) or not decision.get('ok'):
        return {'status':'UNAVAILABLE','reason':'NO_VERIFIED_DECISION','version':VERSION}
    d=decision.get('candidate_direction')
    if d not in ('LONG','SHORT'):
        return {'status':'WAIT','direction':None,'entry_mode':'NONE','reason':'NO_DIRECTIONAL_CONSENSUS','version':VERSION}
    s=1 if d=='LONG' else -1
    px=_num(decision.get('entry')); atr=_num((decision.get('indicators') or {}).get('atr14'))
    geom=decision.get('structural_geometry') or {}; br=geom.get('breakout') or {}
    obstacle=_num(geom.get('obstacle_price')); obstacle_dist=_num(geom.get('obstacle_distance_pct'))
    continuation=bool(geom.get('continuation_strong')); breakout=bool(br.get('confirmed'))
    qualified=bool(decision.get('production_signal_qualified'))
    execution=bool(decision.get('execution_ready'))
    if px is None or atr is None or atr<=0:
        return {'status':'WAIT','direction':d,'entry_mode':'NONE','reason':'ATR_OR_PRICE_UNAVAILABLE','version':VERSION}

    # Structural stop first. If no usable swing is exposed by the verified
    # geometry, ATR supplies a volatility-aware invalidation distance.
    base_stop=px-s*atr*1.2
    entry=px; mode='NOW'; trigger='Verified Production setup is executable now.'
    reference=obstacle

    # If current Production geometry is ready, NOW is the canonical plan.
    # Otherwise choose a better conditional entry instead of printing dashes.
    if not execution:
        if obstacle is not None and obstacle_dist is not None and obstacle_dist<=1.5:
            buffer=max(atr*.10,abs(obstacle)*.0005)
            entry=obstacle+s*buffer
            mode='BREAKOUT'
            trigger=('Buy only after 1H close/hold above ' if d=='LONG' else 'Sell only after 1H close/hold below ')+f'{obstacle:.8g}.'
            base_stop=entry-s*atr*.85
        else:
            entry=px-s*atr*.35
            mode='PULLBACK'
            trigger='Enter only if the pullback holds trend structure and directional evidence remains valid.'
            base_stop=entry-s*atr*.9

    stop=base_stop
    risk=abs(entry-stop)
    # TP1 is deliberately at least 1R. A nearby structure can be used only if
    # it is beyond 1R; otherwise it is not a useful profit target.
    one_r=entry+s*risk
    structural_tp=obstacle if obstacle is not None and ((d=='LONG' and obstacle>one_r) or (d=='SHORT' and obstacle<one_r)) else None
    tp1=structural_tp if structural_tp is not None else one_r
    extension_mult=2.2 if continuation or breakout else 1.8
    tp2=entry+s*max(risk*2.0,atr*extension_mult)
    if d=='LONG' and tp2<=tp1: tp2=tp1+max(risk,atr*.8)
    if d=='SHORT' and tp2>=tp1: tp2=tp1-max(risk,atr*.8)
    rr1=_rr(entry,stop,tp1); rr2=_rr(entry,stop,tp2)
    status='ACTIONABLE' if execution and qualified else 'CONDITIONAL'
    action=('BUY' if d=='LONG' else 'SELL') if status=='ACTIONABLE' else ('BUY_ONLY_IF' if d=='LONG' else 'SELL_ONLY_IF')
    return {
        'version':VERSION,'status':status,'action':action,'direction':d,'entry_mode':mode,
        'entry':round(entry,10),'entry_trigger':trigger,'stop_loss':round(stop,10),
        'tp1':round(tp1,10),'tp2':round(tp2,10),'rr_tp1':round(rr1,3),'rr_tp2':round(rr2,3),
        'reference_structure':round(reference,10) if reference is not None else None,
        'continuation_strong':continuation,'breakout_confirmed':breakout,
        'qualification_required':68,'production_qualified':qualified,'execution_ready':execution,
        'invalidation':'Cancel/re-evaluate if stop/structure fails or verified direction changes.',
        'can_execute':False,'research_only':True,
    }
