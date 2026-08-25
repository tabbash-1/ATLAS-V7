"""ATLAS Evidence-Bound Trade Council V5.

Production trade_plan is canonical. Shadow counterfactuals remain API-compatible
for research/reliability tests, but can never override an ACTIONABLE Production
plan in best_counterfactual or UI guidance.
"""
from __future__ import annotations
import json, math, urllib.parse
from pathlib import Path

VERSION='ATLAS_AI_TRADE_COUNCIL_V5_CANONICAL_PLAN'
HORIZON='1-3H'

def _num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None

def _clip(v,lo=-1.0,hi=1.0): return max(lo,min(hi,v))

def _evidence(decision):
    ind=decision.get('indicators') or {}; tac=decision.get('tactical_opportunity') or {}; attr=decision.get('score_attribution') or {}
    rsi=_num(ind.get('rsi14')); mom=_num(ind.get('momentum_24h_pct')); rv=_num(ind.get('volume_ratio') or decision.get('relative_volume'))
    lv=_num(decision.get('direction_votes_long')) or 0; sv=_num(decision.get('direction_votes_short')) or 0; rs=_num(decision.get('relative_strength_score'))
    fut=_num(decision.get('futures_score')); shadow_fut=_num(decision.get('futures_shadow_score')); rr=_num(tac.get('risk_reward')); room=_num(tac.get('usable_room_pct') or tac.get('room_to_obstacle_pct'))
    ema20=_num(ind.get('ema20')); ema50=_num(ind.get('ema50')); px=_num(decision.get('entry')); pieces=[]
    def add(name,value,weight,detail,source='production_decision'):
        if value is not None: pieces.append({'name':name,'value':round(_clip(value),3),'weight':weight,'detail':detail,'source':source})
    add('direction_votes',(lv-sv)/4.0,2.1,f'LONG {int(lv)} vs SHORT {int(sv)}')
    if px and ema20 and ema50:add('ema_structure',((px/ema20-1)*120)+((ema20/ema50-1)*80),1.2,f'Price/EMA20/EMA50 structure {px:.6g}/{ema20:.6g}/{ema50:.6g}')
    if rsi is not None:add('rsi',(rsi-50)/25,.7,f'RSI14 {rsi:.1f}')
    if mom is not None:add('momentum',mom/3.0,.9,f'24h momentum {mom:.2f}%')
    if rv is not None:add('relative_volume',(rv-1)*1.2,.75,f'RV {rv:.2f}x')
    if rs is not None:add('relative_strength',(rs-50)/25,1.0,f'RS {rs:.1f}')
    if fut is not None:add('futures',fut/100,1.05,f'Validated futures score {fut:.1f}')
    elif shadow_fut is not None:add('futures_shadow',shadow_fut/100,.55,f'Unvalidated futures shadow {shadow_fut:.1f}','research_futures_shadow')
    if rr is not None:
        d=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0; add('tactical_geometry',d*_clip((rr-.8)/1.5),1.5,f'Tactical RR {rr:.2f}')
    if room is not None:
        d=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0; add('room_to_obstacle',d*_clip(room/2.0),.95,f'Usable room {room:.2f}%')
    if isinstance(attr,dict):
        for name,weight in [('trend_base',.5),('momentum_adjustment',.5),('market_breadth_adjustment',.45),('volume_bonus',.45),('relative_strength_adjustment',.45),('futures_adjustment',.45),('obstacle_adjustment',.7)]:
            pts=_num(attr.get(name))
            if pts is not None and pts!=0:add('scorer_'+name,pts/10.0,weight,f'{name} {pts:+.2f}','production_scorer')
        od=_num(attr.get('obstacle_distance_pct'))
        if od is not None:add('obstacle_distance',_clip((od-.6)/1.2),.5,f'Obstacle distance {od:.3f}%','production_scorer')
    return pieces

def _side_score(ev,side):
    sign=1 if side=='LONG' else -1; total=sum(x['weight'] for x in ev) or 1
    return sum(sign*x['value']*x['weight'] for x in ev)/total

def _breakout_anchor(decision,direction,px):
    geom=decision.get('structural_geometry') or {}; br=geom.get('breakout') or {}; obstacle=_num(geom.get('obstacle_price')); range_level=_num(br.get('prior_24h_high') if direction=='LONG' else br.get('prior_24h_low')); c=[]
    if direction=='LONG':
        if obstacle is not None and obstacle>px:c.append((obstacle,geom.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level>px:c.append((range_level,'PRIOR_24H_HIGH'))
        return max(c,key=lambda x:x[0]) if c else (None,None)
    if direction=='SHORT':
        if obstacle is not None and obstacle<px:c.append((obstacle,geom.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level<px:c.append((range_level,'PRIOR_24H_LOW'))
        return min(c,key=lambda x:x[0]) if c else (None,None)
    return None,None

def _canonical_action(decision):
    p=decision.get('trade_plan') or {}
    if p.get('status') in ('ACTIONABLE','CONDITIONAL'):
        return {'status':p.get('status'),'action':p.get('action'),'direction':p.get('direction'),'entry_mode':p.get('entry_mode'),'entry':p.get('entry'),'stop_loss':p.get('stop_loss'),'tp1':p.get('tp1'),'tp2':p.get('tp2'),'rr_tp1':p.get('rr_tp1'),'rr_tp2':p.get('rr_tp2'),'entry_trigger':p.get('entry_trigger'),'source':'production_trade_plan'}
    return {'status':'WAIT','action':'WAIT','direction':decision.get('candidate_direction'),'source':'production_trade_plan'}

def _counterfactuals(decision,direction,confidence=None):
    p=decision.get('trade_plan') or {}; px=_num(decision.get('entry')); atr=_num((decision.get('indicators') or {}).get('atr14'))
    if not px:return []
    scenarios=[]
    if p.get('status')=='ACTIONABLE' and p.get('direction') in ('LONG','SHORT'):
        scenarios.append({'scenario':'PRODUCTION_NOW','direction':p.get('direction'),'entry':p.get('entry'),'stop_loss':p.get('stop_loss'),'target':p.get('tp2'),'tp1':p.get('tp1'),'risk_reward':p.get('rr_tp2'),'trigger':p.get('entry_trigger'),'thesis':'Canonical verified Production plan.','shadow_only':False,'canonical':True})
        return scenarios
    if p.get('status')=='CONDITIONAL' and p.get('direction') in ('LONG','SHORT'):
        scenarios.append({'scenario':'PRODUCTION_CONDITIONAL','direction':p.get('direction'),'entry':p.get('entry'),'stop_loss':p.get('stop_loss'),'target':p.get('tp2'),'tp1':p.get('tp1'),'risk_reward':p.get('rr_tp2'),'trigger':p.get('entry_trigger'),'thesis':'Canonical conditional Production plan.','shadow_only':False,'canonical':True})
    s=1 if direction=='LONG' else -1; atr=atr or px*.01; tac=decision.get('tactical_opportunity') or {}; target=_num(tac.get('target')); stop=_num(tac.get('stop_loss'))
    def add(name,entry,sl,tp,trigger,thesis,**extra):
        risk=abs(entry-sl); reward=abs(tp-entry); row={'scenario':name,'direction':direction,'entry':round(entry,10),'stop_loss':round(sl,10),'target':round(tp,10),'risk_reward':round(reward/risk,3) if risk else None,'trigger':trigger,'thesis':thesis,'shadow_only':True,'canonical':False}; row.update(extra); scenarios.append(row)
    add('ENTER_NOW',px,stop or px-s*atr*.65,target or px+s*atr*1.2,'Immediate only if current evidence remains valid','Shadow comparison only; cannot override Production.')
    pull=px-s*atr*.35; add('WAIT_PULLBACK',pull,pull-s*atr*.75,target or pull+s*atr*1.5,'Price retraces ~0.35 ATR without structure failure','Trade a better entry only after requalification.')
    level,source=_breakout_anchor(decision,direction,px)
    if level is not None:
        buffer=max(atr*.10,abs(level)*.0005); brk=level+s*buffer; relation='above' if direction=='LONG' else 'below'
        add('WAIT_BREAKOUT',brk,brk-s*atr*.75,brk+s*atr*1.6,f'1H price closes/holds {relation} {level:.8g} ({source}) with confirmation','Enter only after actual blocking structure is cleared.',reference_level=round(level,10),reference_source=source,structure_anchored=True,confirmation_buffer=round(buffer,10))
    scenarios.append({'scenario':'REJECT','direction':None,'entry':None,'stop_loss':None,'target':None,'risk_reward':None,'trigger':'No setup reaches acceptable evidence + geometry','thesis':'Preserve capital.','shadow_only':True,'canonical':False})
    return scenarios

def analyze(decision):
    ev=_evidence(decision); bull=_side_score(ev,'LONG'); bear=_side_score(ev,'SHORT'); net=bull-bear; direction='LONG' if net>=0 else 'SHORT'; strength=abs(net)/2
    tac=decision.get('tactical_opportunity') or {}; rr=_num(tac.get('risk_reward')); prod_dir=decision.get('candidate_direction'); prod_ok=bool(decision.get('production_signal_qualified') or decision.get('signal_qualified')); execution=bool(decision.get('execution_ready')); agree=(prod_dir==direction) if prod_dir else False
    if execution and prod_ok: verdict='CONFIRM_PRODUCTION' if agree else 'PRODUCTION_PRIORITY'; reason='CANONICAL_PRODUCTION_ACTIONABLE'; hybrid='CONFIRM'
    elif rr is not None and rr<.8: verdict='REJECT'; reason='RISK_GEOMETRY_FAIL'; hybrid='REJECT'
    elif strength>=.42 and tac.get('direction') in (direction,None): verdict='TAKE_SHADOW'; reason='EVIDENCE_CONVERGENCE'; hybrid='AI_SHADOW_OPPORTUNITY' if not prod_ok else 'CONFIRM' if agree else 'CONFLICT_REVIEW'
    elif strength>=.24: verdict='WATCH'; reason='PARTIAL_CONVERGENCE'; hybrid='WAIT'
    else: verdict='WAIT'; reason='CONFLICTING_EVIDENCE'; hybrid='WAIT'
    confidence=round(max(50,min(92,50+strength*45))); scenarios=_counterfactuals(decision,direction,confidence); canonical=_canonical_action(decision)
    if canonical.get('status')=='ACTIONABLE': best=next((x for x in scenarios if x.get('scenario')=='PRODUCTION_NOW'),None)
    elif canonical.get('status')=='CONDITIONAL': best=next((x for x in scenarios if x.get('scenario')=='PRODUCTION_CONDITIONAL'),None)
    else:
        viable=[x for x in scenarios if x.get('scenario')!='REJECT' and x.get('risk_reward') is not None]; viable.sort(key=lambda x:(x.get('risk_reward') or 0,1 if x.get('scenario')=='WAIT_BREAKOUT' else 0),reverse=True); best=viable[0] if viable and (viable[0].get('risk_reward') or 0)>=.8 else next((x for x in scenarios if x.get('scenario')=='REJECT'),None)
    bull_top=sorted(ev,key=lambda x:x['value']*x['weight'],reverse=True)[:5]; bear_top=sorted(ev,key=lambda x:-x['value']*x['weight'],reverse=True)[:5]
    return {'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','symbol':decision.get('symbol'),'horizon':HORIZON,'generated_at':decision.get('generated_at'),'entry':decision.get('entry'),'direction':prod_dir or direction,'verdict':verdict,'confidence':confidence,'reason':reason,'canonical_action':canonical,'bull_analyst':{'score':round(bull,3),'best_case':[x['detail'] for x in bull_top if x['value']>0]},'bear_analyst':{'score':round(bear,3),'best_case':[x['detail'] for x in bear_top if x['value']<0]},'judge':{'net_strength':round(strength,3),'tactical_rr':rr,'canonical_trade_plan':decision.get('trade_plan'),'invalidation':'Production trade_plan is canonical while actionable.'},'counterfactuals':scenarios,'best_counterfactual':best,'hybrid_judge':{'decision':hybrid,'production_direction':prod_dir,'production_score':_num(decision.get('score')),'production_qualified':prod_ok,'execution_ready':execution,'ai_direction':direction,'ai_verdict':verdict,'agreement':agree,'production_priority':execution},'evidence':ev,'production_decision':decision.get('decision'),'production_score':decision.get('score'),'production_qualified':prod_ok,'safety':{'can_execute':False,'can_change_threshold':False,'can_override_production':False,'production_trade_plan_canonical':True}}

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
            with ledger.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n'); return True
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
            return self._json({'ok':True,'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','can_execute':False,'counterfactuals':True,'production_trade_plan_canonical':True},200)
        return original(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/ai/council','production_trade_plan_canonical':True}
