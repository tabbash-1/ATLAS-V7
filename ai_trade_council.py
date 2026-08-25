"""ATLAS AI Trade Council V5 — canonical Production plan.

The Production `trade_plan` is the single user-facing action contract. AI may
explain or research alternatives, but an ACTIONABLE Production plan is always
returned as the best action and can never be replaced by WAIT/PULLBACK/BREAKOUT.
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


def _evidence(d):
    ind=d.get('indicators') or {}; tac=d.get('tactical_opportunity') or {}; attr=d.get('score_attribution') or {}; out=[]
    def add(name,value,weight,detail,source='production_decision'):
        if value is not None: out.append({'name':name,'value':round(_clip(value),3),'weight':weight,'detail':detail,'source':source})
    lv=_num(d.get('direction_votes_long')) or 0; sv=_num(d.get('direction_votes_short')) or 0
    add('direction_votes',(lv-sv)/4,2.1,f'LONG {int(lv)} vs SHORT {int(sv)}')
    px=_num(d.get('entry')); e20=_num(ind.get('ema20')); e50=_num(ind.get('ema50'))
    if px and e20 and e50:add('ema_structure',((px/e20-1)*120)+((e20/e50-1)*80),1.2,f'Price/EMA20/EMA50 structure {px:.6g}/{e20:.6g}/{e50:.6g}')
    rsi=_num(ind.get('rsi14')); mom=_num(ind.get('momentum_24h_pct')); rv=_num(ind.get('volume_ratio'))
    if rv is None: rv=_num(d.get('relative_volume'))
    rs=_num(d.get('relative_strength_score')); fut=_num(d.get('futures_score')); sf=_num(d.get('futures_shadow_score'))
    if rsi is not None:add('rsi',(rsi-50)/25,.7,f'RSI14 {rsi:.1f}')
    if mom is not None:add('momentum',mom/3,.9,f'24h momentum {mom:.2f}%')
    if rv is not None:add('relative_volume',(rv-1)*1.2,.75,f'RV {rv:.2f}x')
    if rs is not None:add('relative_strength',(rs-50)/25,1.0,f'RS {rs:.1f}')
    if fut is not None:add('futures',fut/100,1.05,f'Validated futures score {fut:.1f}')
    elif sf is not None:add('futures_shadow',sf/100,.55,f'Unvalidated futures shadow {sf:.1f}','research_futures_shadow')
    trr=_num(tac.get('risk_reward'))
    if trr is not None:
        s=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0
        add('tactical_geometry',s*_clip((trr-.8)/1.5),1.5,f'Tactical RR {trr:.2f}')
    for name,w in [('trend_base',.5),('momentum_adjustment',.5),('market_breadth_adjustment',.45),('volume_bonus',.45),('relative_strength_adjustment',.45),('futures_adjustment',.45),('obstacle_adjustment',.7)]:
        pts=_num(attr.get(name))
        if pts is not None and pts!=0:add('scorer_'+name,pts/10,w,f'{name} {pts:+.2f}','production_scorer')
    return out


def _side_score(ev,side):
    sign=1 if side=='LONG' else -1; total=sum(x['weight'] for x in ev) or 1
    return sum(sign*x['value']*x['weight'] for x in ev)/total


def _breakout_anchor(d,direction,px):
    g=d.get('structural_geometry') or {}; br=g.get('breakout') or {}; obstacle=_num(g.get('obstacle_price'))
    range_level=_num(br.get('prior_24h_high') if direction=='LONG' else br.get('prior_24h_low')); c=[]
    if direction=='LONG':
        if obstacle is not None and obstacle>px:c.append((obstacle,g.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level>px:c.append((range_level,'PRIOR_24H_HIGH'))
        return max(c,key=lambda x:x[0]) if c else (None,None)
    if direction=='SHORT':
        if obstacle is not None and obstacle<px:c.append((obstacle,g.get('source') or 'STRUCTURAL_OBSTACLE'))
        if range_level is not None and range_level<px:c.append((range_level,'PRIOR_24H_LOW'))
        return min(c,key=lambda x:x[0]) if c else (None,None)
    return None,None


def _canonical_action(d):
    p=d.get('trade_plan') or {}; status=p.get('status')
    if status in ('ACTIONABLE','CONDITIONAL'):
        return {'status':status,'action':p.get('action'),'direction':p.get('direction'),'entry_mode':p.get('entry_mode'),'entry':p.get('entry'),'stop_loss':p.get('stop_loss'),'tp1':p.get('tp1'),'tp2':p.get('tp2'),'rr_tp1':p.get('rr_tp1'),'rr_tp2':p.get('rr_tp2'),'entry_trigger':p.get('entry_trigger'),'source':'production_trade_plan'}
    return {'status':'WAIT','action':'WAIT','direction':d.get('candidate_direction'),'source':'production_trade_plan'}


def _production_row(p,conditional=False):
    return {'scenario':'PRODUCTION_CONDITIONAL' if conditional else 'PRODUCTION_NOW','direction':p.get('direction'),'entry':p.get('entry'),'stop_loss':p.get('stop_loss'),'target':p.get('tp2'),'tp1':p.get('tp1'),'risk_reward':p.get('rr_tp2'),'trigger':p.get('entry_trigger'),'thesis':'Canonical Production trade plan.','shadow_only':False,'canonical':True}


def _counterfactuals(d,direction,confidence=None):
    p=d.get('trade_plan') or {}; status=p.get('status')
    if status=='ACTIONABLE' and p.get('direction') in ('LONG','SHORT'): return [_production_row(p,False)]
    px=_num(d.get('entry'))
    if px is None:return []
    rows=[]
    if status=='CONDITIONAL' and p.get('direction') in ('LONG','SHORT'): rows.append(_production_row(p,True))
    atr=_num((d.get('indicators') or {}).get('atr14')) or px*.01; s=1 if direction=='LONG' else -1; tac=d.get('tactical_opportunity') or {}; target=_num(tac.get('target')); stop=_num(tac.get('stop_loss'))
    def add(name,entry,sl,tp,trigger,thesis,**extra):
        risk=abs(entry-sl); reward=abs(tp-entry); row={'scenario':name,'direction':direction,'entry':round(entry,10),'stop_loss':round(sl,10),'target':round(tp,10),'risk_reward':round(reward/risk,3) if risk else None,'trigger':trigger,'thesis':thesis,'shadow_only':True,'canonical':False}; row.update(extra); rows.append(row)
    add('ENTER_NOW',px,stop or px-s*atr*.65,target or px+s*atr*1.2,'Immediate only if current evidence remains valid','Shadow comparison only.')
    pull=px-s*atr*.35; add('WAIT_PULLBACK',pull,pull-s*atr*.75,target or pull+s*atr*1.5,'Price retraces ~0.35 ATR without structure failure','Requalify after a better entry.')
    level,source=_breakout_anchor(d,direction,px)
    if level is not None:
        buffer=max(atr*.10,abs(level)*.0005); brk=level+s*buffer; relation='above' if direction=='LONG' else 'below'
        add('WAIT_BREAKOUT',brk,brk-s*atr*.75,brk+s*atr*1.6,f'1H price closes/holds {relation} {level:.8g} ({source}) with confirmation','Enter only after actual blocking structure is cleared.',reference_level=round(level,10),reference_source=source,structure_anchored=True,confirmation_buffer=round(buffer,10))
    rows.append({'scenario':'REJECT','direction':None,'entry':None,'stop_loss':None,'target':None,'risk_reward':None,'trigger':'No acceptable setup','thesis':'Preserve capital.','shadow_only':True,'canonical':False})
    return rows


def analyze(d):
    plan=d.get('trade_plan') or {}; canonical=_canonical_action(d); prod_dir=d.get('candidate_direction'); prod_ok=bool(d.get('production_signal_qualified') or d.get('signal_qualified')); execution=bool(d.get('execution_ready'))
    ev=_evidence(d); bull=_side_score(ev,'LONG'); bear=_side_score(ev,'SHORT'); ai_dir='LONG' if bull-bear>=0 else 'SHORT'; strength=abs(bull-bear)/2; agree=(prod_dir==ai_dir) if prod_dir else False
    tac=d.get('tactical_opportunity') or {}; trr=_num(tac.get('risk_reward')); confidence=round(max(50,min(92,50+strength*45)))
    # Hard canonical invariant: actionable Production is returned immediately as
    # the best action. No RR sort or AI opinion is allowed to replace it.
    if canonical.get('status')=='ACTIONABLE':
        best=_production_row(plan,False); verdict='CONFIRM_PRODUCTION' if agree else 'PRODUCTION_PRIORITY'; hybrid='CONFIRM'; reason='CANONICAL_PRODUCTION_ACTIONABLE'
    else:
        rows=_counterfactuals(d,ai_dir,confidence)
        if canonical.get('status')=='CONDITIONAL': best=_production_row(plan,True)
        else:
            viable=[x for x in rows if x.get('scenario')!='REJECT' and x.get('risk_reward') is not None]; viable.sort(key=lambda x:(x.get('risk_reward') or 0,1 if x.get('scenario')=='WAIT_BREAKOUT' else 0),reverse=True); best=viable[0] if viable and (viable[0].get('risk_reward') or 0)>=.8 else next((x for x in rows if x.get('scenario')=='REJECT'),None)
        if trr is not None and trr<.8: verdict='REJECT'; hybrid='REJECT'; reason='RISK_GEOMETRY_FAIL'
        elif strength>=.42 and tac.get('direction') in (ai_dir,None): verdict='TAKE_SHADOW'; hybrid='AI_SHADOW_OPPORTUNITY' if not prod_ok else 'CONFIRM' if agree else 'CONFLICT_REVIEW'; reason='EVIDENCE_CONVERGENCE'
        elif strength>=.24: verdict='WATCH'; hybrid='WAIT'; reason='PARTIAL_CONVERGENCE'
        else: verdict='WAIT'; hybrid='WAIT'; reason='CONFLICTING_EVIDENCE'
    rows=_counterfactuals(d,ai_dir,confidence)
    bull_top=sorted(ev,key=lambda x:x['value']*x['weight'],reverse=True)[:5]; bear_top=sorted(ev,key=lambda x:-x['value']*x['weight'],reverse=True)[:5]
    return {'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','symbol':d.get('symbol'),'horizon':HORIZON,'generated_at':d.get('generated_at'),'entry':d.get('entry'),'direction':prod_dir or ai_dir,'verdict':verdict,'confidence':confidence,'reason':reason,'canonical_action':canonical,'bull_analyst':{'score':round(bull,3),'best_case':[x['detail'] for x in bull_top if x['value']>0]},'bear_analyst':{'score':round(bear,3),'best_case':[x['detail'] for x in bear_top if x['value']<0]},'judge':{'net_strength':round(strength,3),'tactical_rr':trr,'canonical_trade_plan':plan,'invalidation':'Production trade_plan is canonical while actionable.'},'counterfactuals':rows,'best_counterfactual':best,'hybrid_judge':{'decision':hybrid,'production_direction':prod_dir,'production_score':_num(d.get('score')),'production_qualified':prod_ok,'execution_ready':execution,'ai_direction':ai_dir,'ai_verdict':verdict,'agreement':agree,'production_priority':execution},'evidence':ev,'production_decision':d.get('decision'),'production_score':d.get('score'),'production_qualified':prod_ok,'safety':{'can_execute':False,'can_change_threshold':False,'can_override_production':False,'production_trade_plan_canonical':True}}


def install(atlas):
    ledger=Path(getattr(atlas,'DATA',Path('.')))/'ai_trade_council.jsonl'; original=getattr(atlas.Handler,'do_GET')
    def _append(row):
        try:
            ledger.parent.mkdir(parents=True,exist_ok=True)
            with ledger.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')
            return True
        except Exception:return False
    def council(symbol):
        row=analyze(atlas.production_decision(symbol)); row['stored']=_append(row); return row
    atlas.ai_trade_council=council
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/ai/council':
            q=urllib.parse.parse_qs(u.query); symbol=q.get('symbol',['BTCUSDT'])[0].upper().replace('BINANCE:','')
            try:return self._json(council(symbol),200)
            except Exception as exc:return self._json({'ok':False,'source':VERSION,'error':f'{type(exc).__name__}: {exc}'},500)
        if u.path=='/api/ai/council/status': return self._json({'ok':True,'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','can_execute':False,'counterfactuals':True,'structure_anchored_breakouts':True,'production_trade_plan_canonical':True},200)
        return original(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/ai/council','production_trade_plan_canonical':True}
