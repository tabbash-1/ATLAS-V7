"""ATLAS Evidence-Bound Trade Council V4.

Research-only shadow analyst. It never executes trades and never weakens the
Production gate. V4 fixes conditional breakout geometry so a breakout entry
cannot be placed before the resistance/support it claims to break.
"""
from __future__ import annotations
import json, math, urllib.parse
from pathlib import Path

VERSION = 'ATLAS_AI_TRADE_COUNCIL_V4_STRUCTURE_ANCHORED'
HORIZON = '1-3H'


def _num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None


def _clip(v, lo=-1.0, hi=1.0): return max(lo,min(hi,v))


def _evidence(decision):
    ind=decision.get('indicators') or {}; tac=decision.get('tactical_opportunity') or {}; attr=decision.get('score_attribution') or {}
    rsi=_num(ind.get('rsi14')); mom=_num(ind.get('momentum_24h_pct')); rv=_num(ind.get('volume_ratio') or decision.get('relative_volume'))
    lv=_num(decision.get('direction_votes_long')) or 0; sv=_num(decision.get('direction_votes_short')) or 0
    rs=_num(decision.get('relative_strength_score')); fut=_num(decision.get('futures_score')); shadow_fut=_num(decision.get('futures_shadow_score')); rr=_num(tac.get('risk_reward'))
    room=_num(tac.get('usable_room_pct') or tac.get('room_to_obstacle_pct'))
    ema20=_num(ind.get('ema20')); ema50=_num(ind.get('ema50')); px=_num(decision.get('entry'))
    pieces=[]
    def add(name,value,weight,detail,source='production_decision'):
        if value is not None: pieces.append({'name':name,'value':round(_clip(value),3),'weight':weight,'detail':detail,'source':source})
    add('direction_votes',(lv-sv)/4.0,2.1,f'LONG {int(lv)} vs SHORT {int(sv)}')
    if px and ema20 and ema50:
        trend=((px/ema20-1)*120)+((ema20/ema50-1)*80)
        add('ema_structure',trend,1.2,f'Price/EMA20/EMA50 structure {px:.6g}/{ema20:.6g}/{ema50:.6g}')
    if rsi is not None:add('rsi',(rsi-50)/25,.7,f'RSI14 {rsi:.1f}')
    if mom is not None:add('momentum',mom/3.0,.9,f'24h momentum {mom:.2f}%')
    if rv is not None:add('relative_volume',(rv-1)*1.2,.75,f'RV {rv:.2f}x')
    if rs is not None:add('relative_strength',(rs-50)/25,1.0,f'RS {rs:.1f}')
    if fut is not None:
        add('futures',fut/100,1.05,f'Validated futures score {fut:.1f}','production_decision')
    elif shadow_fut is not None:
        provider=decision.get('futures_shadow_provider') or decision.get('futures_provider') or 'UNKNOWN_PROVIDER'
        add('futures_shadow',shadow_fut/100,.55,f'Unvalidated provider-specific futures shadow {shadow_fut:.1f} via {provider}','research_futures_shadow')
    if rr is not None:
        d=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0
        add('tactical_geometry',d*_clip((rr-.8)/1.5),1.5,f'Tactical RR {rr:.2f}')
    if room is not None:
        d=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0
        add('room_to_obstacle',d*_clip(room/2.0),.95,f'Usable room {room:.2f}%')
    if isinstance(attr,dict):
        for name,weight in [('trend_base',.5),('volume_bonus',.45),('relative_strength_adjustment',.45),('futures_adjustment',.45),('obstacle_adjustment',.7)]:
            pts=_num(attr.get(name))
            if pts is not None and pts!=0:add('scorer_'+name,pts/10.0,weight,f'{name} {pts:+.2f}','production_scorer')
        od=_num(attr.get('obstacle_distance_pct'))
        if od is not None:add('obstacle_distance',_clip((od-.6)/1.2),.5,f'Obstacle distance {od:.3f}%','production_scorer')
    return pieces


def _side_score(evidence, side):
    sign=1 if side=='LONG' else -1
    total=sum(x['weight'] for x in evidence) or 1
    return sum(sign*x['value']*x['weight'] for x in evidence)/total


def _breakout_anchor(decision, direction, px):
    """Return the actual structure that price must clear before a breakout entry."""
    geom=decision.get('structural_geometry') or {}
    br=geom.get('breakout') or {}
    obstacle=_num(geom.get('obstacle_price'))
    range_level=_num(br.get('prior_24h_high') if direction=='LONG' else br.get('prior_24h_low'))
    candidates=[]
    if direction=='LONG':
        if obstacle is not None and obstacle>px:candidates.append((obstacle,geom.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level>px:candidates.append((range_level,'PRIOR_24H_HIGH'))
        if not candidates:return None,None
        # A LONG breakout must clear every relevant resistance ahead, therefore
        # use the highest nearby structural boundary, not an ATR guess below it.
        return max(candidates,key=lambda x:x[0])
    if direction=='SHORT':
        if obstacle is not None and obstacle<px:candidates.append((obstacle,geom.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level<px:candidates.append((range_level,'PRIOR_24H_LOW'))
        if not candidates:return None,None
        # A SHORT breakdown must clear every relevant support below price.
        return min(candidates,key=lambda x:x[0])
    return None,None


def _counterfactuals(decision,direction,confidence):
    tac=decision.get('tactical_opportunity') or {}; px=_num(decision.get('entry')); atr=_num((decision.get('indicators') or {}).get('atr14'))
    target=_num(tac.get('target')); stop=_num(tac.get('stop_loss'))
    if not px:return []
    s=1 if direction=='LONG' else -1
    atr=atr or px*.01
    scenarios=[]
    def add(name,entry,sl,tp,trigger,thesis,**extra):
        risk=abs(entry-sl) if sl is not None else None; reward=abs(tp-entry) if tp is not None else None; xrr=(reward/risk) if risk and reward is not None else None
        row={'scenario':name,'direction':direction,'entry':round(entry,10),'stop_loss':round(sl,10) if sl is not None else None,'target':round(tp,10) if tp is not None else None,'risk_reward':round(xrr,3) if xrr is not None else None,'trigger':trigger,'thesis':thesis,'shadow_only':True}
        row.update(extra); scenarios.append(row)
    add('ENTER_NOW',px,stop or px-s*atr*.65,target or px+s*atr*1.2,'Immediate only if current evidence remains valid','Capture current move without waiting for a better price.')
    pull=px-s*atr*.35
    add('WAIT_PULLBACK',pull,pull-s*atr*.75,target or pull+s*atr*1.5,'Price retraces ~0.35 ATR without structure failure','Trade better entry quality if trend survives the pullback.')

    level,source=_breakout_anchor(decision,direction,px)
    if level is not None:
        # Require a small confirmation buffer beyond the actual structural level.
        buffer=max(atr*.10,abs(level)*.0005)
        brk=level+s*buffer
        sl=brk-s*atr*.75
        tp=brk+s*atr*1.6
        relation='above' if direction=='LONG' else 'below'
        add('WAIT_BREAKOUT',brk,sl,tp,
            f'1H price closes/holds {relation} {level:.8g} ({source}) with confirmation',
            'Enter only after the actual blocking structure has been cleared.',
            reference_level=round(level,10),reference_source=source,structure_anchored=True,confirmation_buffer=round(buffer,10))

    scenarios.append({'scenario':'REJECT','direction':None,'entry':None,'stop_loss':None,'target':None,'risk_reward':None,'trigger':'No setup reaches acceptable evidence + geometry','thesis':'Preserve capital when alternatives are weak.','shadow_only':True})
    return scenarios


def analyze(decision):
    ev=_evidence(decision); bull=_side_score(ev,'LONG'); bear=_side_score(ev,'SHORT'); net=bull-bear
    direction='LONG' if net>=0 else 'SHORT'; strength=abs(net)/2; tac=decision.get('tactical_opportunity') or {}; rr=_num(tac.get('risk_reward'))
    bull_top=sorted(ev,key=lambda x:x['value']*x['weight'],reverse=True)[:5]; bear_top=sorted(ev,key=lambda x:-x['value']*x['weight'],reverse=True)[:5]
    missing=[]
    if decision.get('relative_strength_score') is None: missing.append('relative_strength_score')
    if decision.get('futures_score') is None and decision.get('futures_shadow_score') is None: missing.append('futures_context')
    if not ev: verdict='WAIT'; reason='NO_STRUCTURED_EVIDENCE'
    elif rr is not None and rr<.8: verdict='REJECT'; reason='RISK_GEOMETRY_FAIL'
    elif strength>=.42 and tac.get('direction') in (direction,None): verdict='TAKE_SHADOW'; reason='EVIDENCE_CONVERGENCE'
    elif strength>=.24: verdict='WATCH'; reason='PARTIAL_CONVERGENCE'
    else: verdict='WAIT'; reason='CONFLICTING_EVIDENCE'
    confidence=round(max(50,min(92,50+strength*45)))
    scenarios=_counterfactuals(decision,direction,confidence)
    viable=[x for x in scenarios if x['scenario']!='REJECT' and x.get('risk_reward') is not None]
    viable.sort(key=lambda x:(x['risk_reward'],1 if x['scenario']=='WAIT_BREAKOUT' else 0),reverse=True)
    best=viable[0] if viable and viable[0]['risk_reward']>=.8 else next((x for x in scenarios if x['scenario']=='REJECT'),None)
    prod_dir=decision.get('candidate_direction'); prod_score=_num(decision.get('score')); prod_ok=bool(decision.get('signal_qualified'))
    agree=(prod_dir==direction) if prod_dir else False
    if prod_ok and agree and verdict=='TAKE_SHADOW': hybrid='CONFIRM'
    elif prod_ok and not agree: hybrid='CONFLICT_REVIEW'
    elif not prod_ok and verdict=='TAKE_SHADOW' and best and best.get('scenario')!='REJECT': hybrid='AI_SHADOW_OPPORTUNITY'
    elif verdict=='REJECT': hybrid='REJECT'
    else: hybrid='WAIT'
    futures_context={'production_validated':decision.get('futures_score') is not None,'production_score':decision.get('futures_score'),'shadow_score':decision.get('futures_shadow_score'),'shadow_provider':decision.get('futures_shadow_provider') or decision.get('futures_provider'),'shadow_only':bool(decision.get('futures_shadow_score') is not None and decision.get('futures_score') is None),'can_affect_production':False if decision.get('futures_score') is None else True}
    return {'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','symbol':decision.get('symbol'),'horizon':HORIZON,'generated_at':decision.get('generated_at'),'entry':decision.get('entry'),'direction':direction,'verdict':verdict,'confidence':confidence,'reason':reason,'bull_analyst':{'score':round(bull,3),'best_case':[x['detail'] for x in bull_top if x['value']>0]},'bear_analyst':{'score':round(bear,3),'best_case':[x['detail'] for x in bear_top if x['value']<0]},'judge':{'net_strength':round(strength,3),'tactical_rr':rr,'target':tac.get('target'),'stop_loss':tac.get('stop_loss'),'invalidation':'Frozen stop/structure; no post-outcome rewriting.'},'counterfactuals':scenarios,'best_counterfactual':best,'hybrid_judge':{'decision':hybrid,'production_direction':prod_dir,'production_score':prod_score,'production_qualified':prod_ok,'ai_direction':direction,'ai_verdict':verdict,'agreement':agree},'evidence':ev,'futures_context':futures_context,'missing_data':missing,'production_decision':decision.get('decision'),'production_score':decision.get('score'),'production_qualified':prod_ok,'outcome_contract':{'evaluate_after_hours':[1,3,6],'metrics':['directional_return_pct','MFE_pct','MAE_pct','target_hit','stop_hit','realized_R','time_to_target_minutes'],'frozen':True},'safety':{'can_execute':False,'can_change_threshold':False,'can_override_production':False,'freeze_before_outcome':True,'unvalidated_futures_can_affect_production':False}}


def install(atlas):
    ledger=Path(getattr(atlas,'DATA',Path('.')))/'ai_trade_council.jsonl'; original=getattr(atlas.Handler,'do_GET')
    def _append(row):
        ledger.parent.mkdir(parents=True,exist_ok=True); key=(row.get('symbol'),row.get('generated_at'),row.get('entry'),row.get('version'))
        try:
            if ledger.exists():
                for line in ledger.read_text(errors='ignore').splitlines()[-500:]:
                    try:
                        x=json.loads(line)
                        if (x.get('symbol'),x.get('generated_at'),x.get('entry'),x.get('version'))==key:return False
                    except Exception:pass
            with ledger.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
            return True
        except Exception:return False
    def council(symbol):
        d=atlas.production_decision(symbol); row=analyze(d); row['stored']=_append(row); return row
    atlas.ai_trade_council=council
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/ai/council':
            q=urllib.parse.parse_qs(u.query); symbol=q.get('symbol',['BTCUSDT'])[0].upper().replace('BINANCE:','')
            try:return self._json(council(symbol),200)
            except Exception as exc:return self._json({'ok':False,'source':VERSION,'error':f'{type(exc).__name__}: {exc}'},500)
        if u.path=='/api/ai/council/status':
            rows=0
            try:rows=sum(1 for x in ledger.open() if x.strip()) if ledger.exists() else 0
            except Exception:pass
            return self._json({'ok':True,'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','ledger_rows':rows,'ledger':str(ledger),'can_execute':False,'counterfactuals':True,'hybrid_judge':True,'futures_shadow_safe':True,'structure_anchored_breakouts':True},200)
        return original(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/ai/council','mode':'SHADOW_RESEARCH_ONLY','counterfactuals':True,'hybrid_judge':True,'futures_shadow_safe':True,'structure_anchored_breakouts':True}
