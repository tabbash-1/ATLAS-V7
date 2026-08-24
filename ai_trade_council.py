"""ATLAS Evidence-Bound Trade Council.

Research-only shadow analyst. It never executes trades and never weakens the
production gate. The council converts ATLAS-native evidence into independent
Bull, Bear and Judge views, freezes the thesis, and makes it measurable against
future outcomes.

No external LLM dependency is required for V1: the reasoning is deterministic
and auditable. A remote model can later consume the exact same evidence packet
without changing the ledger contract.
"""
from __future__ import annotations
import json, math, os, time, urllib.parse
from pathlib import Path

VERSION = 'ATLAS_AI_TRADE_COUNCIL_V1'
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
    rs=_num(decision.get('relative_strength_score')); fut=_num(decision.get('futures_score')); rr=_num(tac.get('risk_reward'))
    room=_num(tac.get('usable_room_pct') or tac.get('room_to_obstacle_pct'))
    pieces=[]
    def add(name,value,weight,detail):
        if value is not None: pieces.append({'name':name,'value':round(_clip(value),3),'weight':weight,'detail':detail})
    add('direction_votes', (lv-sv)/4.0, 2.0, f'LONG {int(lv)} vs SHORT {int(sv)}')
    if rsi is not None: add('rsi', (rsi-50)/25, .7, f'RSI14 {rsi:.1f}')
    if mom is not None: add('momentum', mom/3.0, .8, f'24h momentum {mom:.2f}%')
    if rv is not None: add('relative_volume', ((rv-1)*1.2), .65, f'RV {rv:.2f}x')
    if rs is not None: add('relative_strength', (rs-50)/25, .9, f'RS {rs:.1f}')
    if fut is not None: add('futures', fut/100, 1.0, f'Futures score {fut:.1f}')
    if rr is not None:
        direction=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0
        add('tactical_geometry', direction*_clip((rr-.8)/1.5), 1.35, f'Tactical RR {rr:.2f}')
    if room is not None:
        direction=1 if tac.get('direction')=='LONG' else -1 if tac.get('direction')=='SHORT' else 0
        add('room_to_obstacle', direction*_clip(room/2.0), .8, f'Usable room {room:.2f}%')
    # Preserve scorer attribution as evidence, but never infer unavailable facts.
    for i,x in enumerate(attr if isinstance(attr,list) else []):
        pts=_num(x.get('points') if isinstance(x,dict) else None)
        if pts: add(f'scorer_{i}', pts/10.0, .35, str(x.get('reason') or x.get('label') or 'production scorer evidence'))
    return pieces


def _side_score(evidence, side):
    sign=1 if side=='LONG' else -1
    total=sum(x['weight'] for x in evidence) or 1
    return sum(sign*x['value']*x['weight'] for x in evidence)/total


def analyze(decision):
    ev=_evidence(decision); bull=_side_score(ev,'LONG'); bear=_side_score(ev,'SHORT')
    bull_top=sorted(ev,key=lambda x:x['value']*x['weight'],reverse=True)[:4]
    bear_top=sorted(ev,key=lambda x:-x['value']*x['weight'],reverse=True)[:4]
    net=bull-bear
    direction='LONG' if net>=0 else 'SHORT'; strength=abs(net)/2
    tac=decision.get('tactical_opportunity') or {}; rr=_num(tac.get('risk_reward'))
    missing=[]
    for key in ('futures_score','relative_strength_score'):
        if decision.get(key) is None: missing.append(key)
    if not ev: verdict='WAIT'; reason='NO_STRUCTURED_EVIDENCE'
    elif rr is not None and rr < .8: verdict='REJECT'; reason='RISK_GEOMETRY_FAIL'
    elif strength >= .42 and tac.get('direction') in (direction,None): verdict='TAKE_SHADOW'; reason='EVIDENCE_CONVERGENCE'
    elif strength >= .24: verdict='WATCH'; reason='PARTIAL_CONVERGENCE'
    else: verdict='WAIT'; reason='CONFLICTING_EVIDENCE'
    confidence=round(max(50,min(91,50+strength*45)))
    return {
      'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','symbol':decision.get('symbol'),'horizon':HORIZON,
      'generated_at':decision.get('generated_at'),'entry':decision.get('entry'),'direction':direction,
      'verdict':verdict,'confidence':confidence,'reason':reason,
      'bull_analyst':{'score':round(bull,3),'best_case':[x['detail'] for x in bull_top if x['value']>0]},
      'bear_analyst':{'score':round(bear,3),'best_case':[x['detail'] for x in bear_top if x['value']<0]},
      'judge':{'net_strength':round(strength,3),'tactical_rr':rr,'target':tac.get('target'),'stop_loss':tac.get('stop_loss'),'invalidation':'Frozen tactical stop/structure; no post-entry rewriting.'},
      'evidence':ev,'missing_data':missing,
      'production_decision':decision.get('decision'),'production_score':decision.get('score'),
      'production_qualified':bool(decision.get('signal_qualified')),
      'safety':{'can_execute':False,'can_change_threshold':False,'can_override_production':False,'freeze_before_outcome':True}
    }


def install(atlas):
    ledger=Path(getattr(atlas,'DATA',Path('.')))/'ai_trade_council.jsonl'
    original=getattr(atlas.Handler,'do_GET')
    def _append(row):
        ledger.parent.mkdir(parents=True,exist_ok=True)
        key=(row.get('symbol'),row.get('generated_at'),row.get('entry'))
        try:
            if ledger.exists():
                for line in ledger.read_text(errors='ignore').splitlines()[-300:]:
                    try:
                        x=json.loads(line)
                        if (x.get('symbol'),x.get('generated_at'),x.get('entry'))==key:return False
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
            try: rows=sum(1 for x in ledger.open() if x.strip()) if ledger.exists() else 0
            except Exception:pass
            return self._json({'ok':True,'version':VERSION,'mode':'SHADOW_RESEARCH_ONLY','ledger_rows':rows,'ledger':str(ledger),'can_execute':False},200)
        return original(self)
    atlas.Handler.do_GET=do_GET
    return {'enabled':True,'version':VERSION,'endpoint':'/api/ai/council','mode':'SHADOW_RESEARCH_ONLY'}
