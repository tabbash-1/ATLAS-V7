"""Single source of truth for the ATLAS browser decision card.

Adds research-only tactical and quick-trade lanes alongside the unchanged
production score decision. The production score threshold is never weakened
here. Production score qualification and execution geometry readiness are
reported separately so a high score cannot masquerade as a good trade plan when
the structural target offers less reward than the stop risk.
"""

from pathlib import Path

from quick_reentry_guard import QuickReentryGuard
from production_signal_scoring import candle_progress, paced_relative_volume

VERSION = "PRODUCTION_DECISION_API_V7_QUICK_REENTRY_GUARD+PACED_VOLUME_V1"
GEOMETRY_MIN_RR = 1.0


def install(atlas):
    original_get = atlas.Handler.do_GET
    guard_path = Path(getattr(atlas, 'DATA', Path('.'))) / 'quick_reentry_guard.json'
    quick_guard = QuickReentryGuard(guard_path)

    def tactical_level(ks, px, direction, fallback=None):
        """Nearest meaningful recent swing level with at least 0.30% room."""
        recent = ks[-96:]
        pts = []
        for i in range(2, len(recent)-2):
            row = recent[i]
            if direction == 'LONG':
                v = row.get('high')
                if v is not None and v >= recent[i-1].get('high', v) and v >= recent[i+1].get('high', v):
                    pts.append(float(v))
            else:
                v = row.get('low')
                if v is not None and v <= recent[i-1].get('low', v) and v <= recent[i+1].get('low', v):
                    pts.append(float(v))
        if direction == 'LONG':
            good = sorted({v for v in pts if v >= px * 1.003})
        else:
            good = sorted({v for v in pts if v <= px * 0.997}, reverse=True)
        if good:
            return good[0], 'RECENT_SWING_LEVEL'
        if fallback is not None:
            room = ((fallback-px)/px*100) if direction == 'LONG' else ((px-fallback)/px*100)
            if room >= 0.30:
                return fallback, 'CLOUD_SR_FALLBACK'
        return None, 'NO_TRADABLE_LEVEL'

    def geometry_assessment(direction, px, stop, target, rr):
        """Execution-quality guard; never modifies the score or signal threshold."""
        if direction not in ('LONG', 'SHORT'):
            return {'status': 'NOT_APPLICABLE', 'qualified': False, 'reason': 'NO_DIRECTION'}
        if stop is None or target is None or rr is None:
            return {
                'status': 'BLOCK', 'qualified': False,
                'reason': 'GEOMETRY_INCOMPLETE', 'min_risk_reward': GEOMETRY_MIN_RR,
            }
        directional = ((direction == 'LONG' and stop < px < target) or
                       (direction == 'SHORT' and target < px < stop))
        if not directional:
            return {
                'status': 'BLOCK', 'qualified': False,
                'reason': 'INVALID_ENTRY_SL_TP_ORDER', 'min_risk_reward': GEOMETRY_MIN_RR,
                'risk_reward': round(rr, 6),
            }
        if rr < GEOMETRY_MIN_RR:
            return {
                'status': 'BLOCK', 'qualified': False,
                'reason': 'RR_BELOW_ONE_TO_ONE', 'min_risk_reward': GEOMETRY_MIN_RR,
                'risk_reward': round(rr, 6),
            }
        return {
            'status': 'PASS', 'qualified': True,
            'reason': 'RR_ONE_TO_ONE_OR_BETTER', 'min_risk_reward': GEOMETRY_MIN_RR,
            'risk_reward': round(rr, 6),
        }

    def active_quick_payload(guard_state, fallback_direction):
        rec = (guard_state or {}).get('record') or {}
        return {
            'status': 'QUICK_TRADE_ACTIVE',
            'direction': rec.get('direction') or fallback_direction,
            'horizon': '1-2H',
            'entry': rec.get('entry'),
            'target': rec.get('target'),
            'stop_loss': rec.get('stop_loss'),
            'risk_reward': rec.get('risk_reward'),
            'confidence': rec.get('confidence') or 0,
            'reason': 'ACTIVE_SAME_DIRECTION_SIGNAL_NOT_REISSUED',
            'active_remaining_seconds': guard_state.get('active_remaining_seconds'),
            'shadow_only': True,
            'can_override_production': False,
        }

    def build_decision(symbol):
        symbol = str(symbol or '').upper().replace('BINANCE:', '')
        if symbol not in atlas.ON_DEMAND_SYMBOLS:
            return {'ok': False, 'error': 'unsupported symbol', 'supported_symbols': list(atlas.ON_DEMAND_SYMBOLS), 'source': VERSION}

        btc = atlas._spot_klines('BTCUSDT')
        ks = btc if symbol == 'BTCUSDT' else atlas._spot_klines(symbol)
        if len(ks) < 100:
            return {'ok': False, 'error': 'insufficient candles', 'source': VERSION}

        closes=[x['close'] for x in ks]; vols=[x['volume'] for x in ks]; px=closes[-1]
        ema20=atlas._ema(closes[-80:],20); ema50=atlas._ema(closes[-120:],50)
        rsi=atlas._rsi(closes,14); atr=atlas._atr(ks,14)
        mom24=((px/closes[-25])-1)*100 if len(closes)>=25 and closes[-25] else 0.0
        long_votes=sum((px>=ema20, ema20>=ema50, rsi>=50, mom24>=0))
        short_votes=sum((px<=ema20, ema20<=ema50, rsi<=50, mom24<=0))
        vol_base=sum(vols[-21:-1])/20 if len(vols)>=21 else vols[-1]
        raw_rv=vols[-1]/vol_base if vol_base else 1.0
        progress=candle_progress(ks[-1])
        rv=paced_relative_volume(raw_rv,progress)
        sup,res,sd,rd=atlas._cloud_sr(ks)

        row=atlas.cloud_score_symbol(symbol,btc); threshold=float(atlas.CLOUD_FORWARD_MIN_SCORE)
        candidate_direction=row.get('direction') if isinstance(row,dict) else None
        score=atlas.fnum(row.get('final_score')) if isinstance(row,dict) else None
        if isinstance(row,dict) and 'production_signal_qualified' in row:
            qualified=bool(row.get('production_signal_qualified'))
        else:
            qualified=bool(candidate_direction in ('LONG','SHORT') and score is not None and score>=threshold)
        decision=candidate_direction if qualified else 'WAIT'
        if row is None: reason='NO_DIRECTIONAL_CONSENSUS' if max(long_votes,short_votes)<3 or long_votes==short_votes else 'SCORER_RETURNED_NO_CANDIDATE'
        elif not qualified: reason='SCORE_BELOW_SIGNAL_THRESHOLD'
        else: reason='SIGNAL_QUALIFIED'

        stop=target=rr=None
        if isinstance(row,dict):
            rr=atlas.fnum(row.get('rr_tp2'))
            if candidate_direction=='LONG' and atr: stop,target=px-atr*1.2,res
            elif candidate_direction=='SHORT' and atr: stop,target=px+atr*1.2,sup

        geometry=geometry_assessment(candidate_direction, px, stop, target, rr)
        execution_ready=bool(qualified and geometry.get('qualified'))
        actionable_decision=candidate_direction if execution_ready else 'WAIT'
        if not qualified:
            actionable_reason=reason
        elif not geometry.get('qualified'):
            actionable_reason=geometry.get('reason')
        else:
            actionable_reason='EXECUTION_READY'

        tactical={'status':'NO_SETUP','direction':None,'horizon':'1-3H','entry':px,'target':None,'stop_loss':None,'risk_reward':None,'room_to_obstacle_pct':None,'confidence':0,'reason':'NO_DIRECTIONAL_CONSENSUS','research_only':True}
        tdir=None
        if long_votes>=3 and long_votes>short_votes: tdir='LONG'
        elif short_votes>=3 and short_votes>long_votes: tdir='SHORT'
        if tdir and atr and atr>0:
            fallback=res if tdir=='LONG' else sup
            obstacle_px, level_source=tactical_level(ks,px,tdir,fallback)
            if obstacle_px is not None:
                room=((obstacle_px-px)/px*100) if tdir=='LONG' else ((px-obstacle_px)/px*100)
                usable=max(0.0,room*0.85)
                target_px=px*(1+usable/100) if tdir=='LONG' else px*(1-usable/100)
                stop_px=px-atr*0.65 if tdir=='LONG' else px+atr*0.65
                risk=abs(px-stop_px); reward=abs(target_px-px); trr=reward/risk if risk>0 else None
                votes=long_votes if tdir=='LONG' else short_votes
                momentum_aligned=(tdir=='LONG' and mom24>=0) or (tdir=='SHORT' and mom24<=0)
                confidence=52+(8 if votes==4 else 3)+(6 if rv>=0.8 else 0)+(4 if momentum_aligned else -4)
                if trr is None or trr<0.8: status,treason='WAIT','TACTICAL_RR_TOO_LOW'
                elif votes==4 and trr>=1.0: status,treason=f'{tdir}_TACTICAL','ROOM_TO_NEXT_SWING_LEVEL'
                elif votes>=3 and trr>=1.2: status,treason=f'{tdir}_TACTICAL','ROOM_TO_NEXT_SWING_LEVEL'
                else: status,treason='WATCH','NEEDS_CONFIRMATION'
                tactical={'status':status,'direction':tdir,'horizon':'1-3H','entry':px,'target':round(target_px,10),'stop_loss':round(stop_px,10),'risk_reward':round(trr,3) if trr is not None else None,'room_to_obstacle_pct':round(room,3),'usable_room_pct':round(usable,3),'confidence':max(0,min(100,confidence)),'reason':treason,'level_source':level_source,'exit_rule':'EXIT_BEFORE_NEXT_SWING_SUPPORT_RESISTANCE','research_only':True}
            else:
                tactical.update({'direction':tdir,'reason':'NO_TRADABLE_SWING_LEVEL'})

        # QUICK TRADE never overrides Production. It only classifies whether a
        # rejected/WAIT setup deserves a 1-2h shadow test. V7 adds a persistent
        # duplicate/re-entry guard: one active same-direction signal at a time,
        # plus a 3h cooldown after a sampled stop breach.
        quick={'status':'WAIT','direction':tdir,'horizon':'1-2H','entry':None,'target':None,'stop_loss':None,'risk_reward':None,'confidence':0,'reason':'NO_QUICK_SETUP','shadow_only':True,'can_override_production':False}
        trr=tactical.get('risk_reward')
        aligned_candidate=bool(tdir and candidate_direction==tdir)
        score_near=bool(score is not None and score >= threshold-12)  # research band, not a production threshold
        strong_votes=max(long_votes,short_votes)>=4 and tdir is not None
        geometry_ok=bool(trr is not None and trr>=0.8 and tactical.get('target') is not None and tactical.get('stop_loss') is not None)
        guard_state = quick_guard.inspect(symbol, tdir, px) if tdir else {'allow_new': True, 'state': 'NO_DIRECTION'}

        if guard_state.get('state') == 'ACTIVE':
            quick = active_quick_payload(guard_state, tdir)
        elif guard_state.get('state') == 'POST_STOP_COOLDOWN':
            quick.update({
                'direction': tdir,
                'reason': 'POST_STOP_REENTRY_COOLDOWN',
                'cooldown_remaining_seconds': guard_state.get('cooldown_remaining_seconds'),
                'reentry_blocked': True,
            })
        elif decision=='WAIT' and tdir and geometry_ok:
            if aligned_candidate and score_near:
                quick={'status':'QUICK_TRADE_SHADOW','direction':tdir,'horizon':'1-2H','entry':px,'target':tactical.get('target'),'stop_loss':tactical.get('stop_loss'),'risk_reward':trr,'confidence':min(88,int(tactical.get('confidence') or 0)+6),'reason':'DIRECTIONAL_CANDIDATE_NEAR_THRESHOLD_WITH_SHORT_TERM_GEOMETRY','exit_rule':'EXIT_AT_OR_BEFORE_NEARBY_SWING_OBSTACLE','shadow_only':True,'can_override_production':False}
                quick_guard.register(symbol,tdir,px,tactical.get('stop_loss'),tactical.get('target'),risk_reward=trr,confidence=quick.get('confidence'),score=score)
            elif strong_votes:
                quick={'status':'WATCH_ONLY','direction':tdir,'horizon':'1-2H','entry':px,'target':tactical.get('target'),'stop_loss':tactical.get('stop_loss'),'risk_reward':trr,'confidence':int(tactical.get('confidence') or 0),'reason':'STRONG_VOTES_BUT_NO_PRODUCTION_CANDIDATE_CONFIRMATION','exit_rule':'WAIT_FOR_BREAKOUT_OR_CANDIDATE_CONFIRMATION','shadow_only':True,'can_override_production':False}
            else:
                quick.update({'direction':tdir,'reason':'INSUFFICIENT_DIRECTIONAL_CONFIRMATION'})
        elif decision!='WAIT':
            quick.update({'direction':candidate_direction,'reason':'PRODUCTION_ALREADY_QUALIFIED'})
        elif tdir and not geometry_ok:
            quick.update({'direction':tdir,'reason':'SHORT_TERM_GEOMETRY_NOT_GOOD_ENOUGH'})

        original_trade_plan=(row or {}).get('trade_plan_status') if isinstance(row,dict) else None
        if qualified and not execution_ready:
            trade_plan_status='SCORE_QUALIFIED_GEOMETRY_BLOCKED'
        elif execution_ready:
            trade_plan_status='EXECUTION_READY'
        else:
            trade_plan_status=original_trade_plan

        return {'ok':True,'source':VERSION,'scoring_version':(row or {}).get('scoring_version') if isinstance(row,dict) else None,'symbol':symbol,'decision':decision,'candidate_direction':candidate_direction,'signal_qualified':qualified,'production_signal_qualified':qualified,'wait_reason':None if qualified else reason,'score':score,'signal_threshold':threshold,'score_gap_to_signal':round(threshold-score,3) if score is not None and score<threshold else 0,'score_attribution':(row or {}).get('score_attribution') if isinstance(row,dict) else None,'entry':px,'stop_loss':stop,'take_profit':target,'risk_reward':rr,'geometry_gate':geometry,'execution_ready':execution_ready,'actionable_decision':actionable_decision,'actionable_reason':actionable_reason,'direction_votes':(row or {}).get('direction_votes') if isinstance(row,dict) else max(long_votes,short_votes),'direction_votes_long':(row or {}).get('direction_votes_long') if isinstance(row,dict) else long_votes,'direction_votes_short':(row or {}).get('direction_votes_short') if isinstance(row,dict) else short_votes,'execution_decision':(row or {}).get('execution_decision') if isinstance(row,dict) else None,'trade_plan_status':trade_plan_status,'playbook':(row or {}).get('playbook_primary') if isinstance(row,dict) else None,'futures_available':(row or {}).get('futures_available') if isinstance(row,dict) else None,'futures_provider':(row or {}).get('futures_provider') if isinstance(row,dict) else None,'futures_score':(row or {}).get('futures_score') if isinstance(row,dict) else None,'relative_strength_score':(row or {}).get('relative_strength_score') if isinstance(row,dict) else None,'volume_quality':(row or {}).get('volume_quality') if isinstance(row,dict) else None,'relative_volume':(row or {}).get('relative_volume') if isinstance(row,dict) else round(rv,3),'volume_pacing':{'raw_relative_volume':round(raw_rv,6),'candle_progress':round(progress,6),'paced_relative_volume':round(rv,6),'source':'SHARED_PRODUCTION_SIGNAL_SCORING_HELPERS'},'regime':(row or {}).get('regime') if isinstance(row,dict) else None,'tactical_opportunity':tactical,'quick_trade_shadow':quick,'timeframe_matrix':{'quick_1_2h':quick,'tactical_1_3h':tactical,'swing':{'status':decision,'direction':candidate_direction,'score':score,'threshold':threshold,'risk_reward':rr,'execution_ready':execution_ready,'actionable_decision':actionable_decision},'macro':{'status':'CONTEXT_ONLY','note':'Daily/weekly independent scorer remains context-only; short-term research never overrides swing safeguards.'}},'indicators':{'ema20':ema20,'ema50':ema50,'rsi14':rsi,'atr14':atr,'volume_ratio':rv,'raw_volume_ratio':raw_rv,'candle_progress':progress,'momentum_24h_pct':mom24},'generated_at':atlas.now_iso(),'research_only':True,'live_execution':False}

    atlas.production_decision=build_decision
    atlas.QUICK_REENTRY_GUARD = quick_guard
    def do_GET(self):
        import urllib.parse
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/decision/current':
            q=urllib.parse.parse_qs(u.query); symbol=q.get('symbol',['BTCUSDT'])[0]
            try:
                result=atlas.production_decision(symbol); return self._json(result,200 if result.get('ok') else 400)
            except Exception as exc:
                return self._json({'ok':False,'error':f'{type(exc).__name__}: {exc}','source':VERSION,'research_only':True,'live_execution':False},500)
        return original_get(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/decision/current','geometry_gate_min_rr':GEOMETRY_MIN_RR,'quick_lane':'1-2H_SHADOW_ONLY','quick_reentry_guard':'PERSISTENT_ACTIVE_DEDUP_PLUS_POST_STOP_COOLDOWN','tactical_lane':'1-3H_RESEARCH_ONLY'}