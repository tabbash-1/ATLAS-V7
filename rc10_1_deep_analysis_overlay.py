"""ATLAS RC10.1 deep technical analysis overlay for the production website.

This module is deliberately read-only/research execution logic: it enriches the
website with a complete 4-12H trade thesis while leaving the existing Production
decision authority and live-execution policy untouched.
"""
import math
import time
import urllib.parse

VERSION = "RC10_1_SITE_DEEP_ANALYSIS_V1"
SUPPORTED = {"BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","HYPEUSDT"}


def _f(x, d=None):
    try: return float(x)
    except Exception: return d


def _ema(vals, n):
    if not vals: return None
    k=2/(n+1); e=float(vals[0])
    for v in vals[1:]: e=float(v)*k+e*(1-k)
    return e


def _rsi(vals,n=14):
    if len(vals)<n+2:return None
    ds=[vals[i]-vals[i-1] for i in range(1,len(vals))]
    g=sum(max(x,0) for x in ds[-n:])/n; l=sum(max(-x,0) for x in ds[-n:])/n
    return 100 if l==0 else 100-(100/(1+g/l))


def _atr(rows,n=14):
    if len(rows)<n+2:return None
    tr=[]
    for i in range(1,len(rows)):
        h,l,pc=rows[i]['high'],rows[i]['low'],rows[i-1]['close']
        tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(tr[-n:])/n


def _klines(atlas,symbol,interval,limit=220):
    urls=[
      f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
      f"https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}",
    ]
    raw=atlas.get_json_fallback(urls,'spot')
    out=[]
    for x in raw:
        out.append({'open_time':int(x[0]),'open':float(x[1]),'high':float(x[2]),'low':float(x[3]),'close':float(x[4]),'volume':float(x[5]),'close_time':int(x[6])})
    return out


def _bias(rows):
    c=[x['close'] for x in rows]
    e20=_ema(c[-100:],20); e50=_ema(c[-160:],50); r=_rsi(c,14); px=c[-1]
    up=sum([px>e20 if e20 else False,e20>e50 if e20 and e50 else False,r>=50 if r is not None else False])
    dn=sum([px<e20 if e20 else False,e20<e50 if e20 and e50 else False,r<=50 if r is not None else False])
    b='LONG' if up>=2 and up>dn else 'SHORT' if dn>=2 and dn>up else 'NEUTRAL'
    return {'bias':b,'close':px,'ema20':e20,'ema50':e50,'rsi14':r,'atr14':_atr(rows,14)}


def _pivots(rows,window=3):
    hi=[]; lo=[]
    for i in range(window,len(rows)-window):
        h=rows[i]['high']; l=rows[i]['low']
        if h==max(x['high'] for x in rows[i-window:i+window+1]): hi.append((i,h))
        if l==min(x['low'] for x in rows[i-window:i+window+1]): lo.append((i,l))
    return hi,lo


def _structure(rows):
    hi,lo=_pivots(rows[-140:],3)
    hs=[x[1] for x in hi[-3:]]; ls=[x[1] for x in lo[-3:]]
    state='RANGE_TRANSITION'
    if len(hs)>=2 and len(ls)>=2:
        if hs[-1]>hs[-2] and ls[-1]>ls[-2]: state='HH_HL'
        elif hs[-1]<hs[-2] and ls[-1]<ls[-2]: state='LH_LL'
    return {'state':state,'swing_highs':hs,'swing_lows':ls,'last_swing_high':hs[-1] if hs else None,'last_swing_low':ls[-1] if ls else None}


def _bos_choch(rows,st):
    px=rows[-1]['close']; prev=rows[-2]['close']; sh=st.get('last_swing_high'); sl=st.get('last_swing_low')
    event='NONE'; direction=None
    if sh and px>sh and prev<=sh: event='BOS_UP' if st['state']=='HH_HL' else 'CHOCH_UP'; direction='LONG'
    elif sl and px<sl and prev>=sl: event='BOS_DOWN' if st['state']=='LH_LL' else 'CHOCH_DOWN'; direction='SHORT'
    return {'event':event,'direction':direction,'level':sh if direction=='LONG' else sl if direction=='SHORT' else None}


def _anchored_vwap(rows,st):
    anchors=[]
    hi,lo=_pivots(rows[-180:],3)
    if hi: anchors.append(hi[-1][0])
    if lo: anchors.append(lo[-1][0])
    start=max(0,min(anchors)) if anchors else max(0,len(rows)-80)
    sub=rows[-180:]
    pv=vol=0.0
    for r in sub[start:]:
        tp=(r['high']+r['low']+r['close'])/3; pv+=tp*r['volume']; vol+=r['volume']
    vwap=pv/vol if vol else None; px=rows[-1]['close']
    return {'value':vwap,'position':'ABOVE' if vwap and px>vwap else 'BELOW' if vwap else 'UNKNOWN'}


def _volume_profile(rows,bins=32):
    xs=rows[-120:]; low=min(x['low'] for x in xs); high=max(x['high'] for x in xs); span=max(high-low,1e-12)
    hist=[0.0]*bins
    for r in xs:
        p=(r['high']+r['low']+r['close'])/3; idx=min(bins-1,max(0,int((p-low)/span*bins))); hist[idx]+=r['volume']
    total=sum(hist); poc_i=max(range(bins),key=lambda i:hist[i]); order=sorted(range(bins),key=lambda i:hist[i],reverse=True)
    chosen=[]; acc=0
    for i in order:
        chosen.append(i); acc+=hist[i]
        if total and acc/total>=.70:break
    def level(i): return low+(i+.5)*span/bins
    poc=level(poc_i); vah=level(max(chosen)); val=level(min(chosen)); px=rows[-1]['close']
    loc='ABOVE_VALUE' if px>vah else 'BELOW_VALUE' if px<val else 'VALUE_AREA'
    return {'poc':poc,'vah':vah,'val':val,'location':loc}


def _volume_delta(rows):
    cvd=0.0; recent=[]
    for r in rows[-80:]:
        rng=max(r['high']-r['low'],1e-12); pos=(r['close']-r['low'])/rng
        d=r['volume']*(2*pos-1); cvd+=d; recent.append(d)
    last=sum(recent[-10:]); prior=sum(recent[-30:-10]) if len(recent)>=30 else 0
    px0=rows[-11]['close']; px=rows[-1]['close']; price_dir=1 if px>px0 else -1 if px<px0 else 0
    delta_dir=1 if last>0 else -1 if last<0 else 0
    div='BEARISH_DIVERGENCE' if price_dir>0 and delta_dir<0 else 'BULLISH_DIVERGENCE' if price_dir<0 and delta_dir>0 else 'NONE'
    return {'cvd_proxy':cvd,'recent_delta':last,'prior_delta':prior,'bias':'BUY' if last>0 else 'SELL' if last<0 else 'NEUTRAL','divergence':div}


def _liquidity(rows):
    hi,lo=_pivots(rows[-120:],2); atr=_atr(rows,14) or 0; tol=max(atr*.18,rows[-1]['close']*.001)
    eqh=[]; eql=[]
    hs=[x[1] for x in hi[-8:]]; ls=[x[1] for x in lo[-8:]]
    for a in hs:
        if sum(abs(a-b)<=tol for b in hs)>=2: eqh.append(a)
    for a in ls:
        if sum(abs(a-b)<=tol for b in ls)>=2: eql.append(a)
    r=rows[-1]; sweep='NONE'
    if eqh and r['high']>max(eqh) and r['close']<max(eqh): sweep='BUY_SIDE_SWEEP_REJECTED'
    if eql and r['low']<min(eql) and r['close']>min(eql): sweep='SELL_SIDE_SWEEP_REJECTED'
    return {'equal_highs':sorted(set(round(x,10) for x in eqh))[-3:],'equal_lows':sorted(set(round(x,10) for x in eql))[:3],'sweep':sweep,'buy_side_target':max(hs) if hs else None,'sell_side_target':min(ls) if ls else None}


def _fvg(rows):
    bull=[]; bear=[]
    xs=rows[-80:]
    for i in range(2,len(xs)):
        if xs[i]['low']>xs[i-2]['high']: bull.append({'low':xs[i-2]['high'],'high':xs[i]['low']})
        if xs[i]['high']<xs[i-2]['low']: bear.append({'low':xs[i]['high'],'high':xs[i-2]['low']})
    return {'bullish':bull[-3:],'bearish':bear[-3:]}


def _order_block(rows,direction):
    xs=rows[-80:]; atr=_atr(rows,14) or 0
    for i in range(len(xs)-3,1,-1):
        cur=xs[i]; nxt=xs[i+1] if i+1<len(xs) else None
        if not nxt: continue
        impulse=abs(nxt['close']-nxt['open'])
        if direction=='LONG' and cur['close']<cur['open'] and nxt['close']>nxt['open'] and impulse>=atr*.7:
            return {'type':'BULLISH_OB','low':cur['low'],'high':cur['high']}
        if direction=='SHORT' and cur['close']>cur['open'] and nxt['close']<nxt['open'] and impulse>=atr*.7:
            return {'type':'BEARISH_OB','low':cur['low'],'high':cur['high']}
    return None


def _historical(rows):
    px=rows[-1]['close']; closes=sorted(x['close'] for x in rows[-180:]); vols=sorted(x['volume'] for x in rows[-180:]); atrs=[]
    for i in range(20,len(rows[-180:])):
        a=_atr(rows[-180:][:i+1],14)
        if a is not None: atrs.append(a)
    def pct(arr,v): return round(100*sum(x<=v for x in arr)/len(arr),1) if arr else None
    a=_atr(rows,14); return {'price_percentile':pct(closes,px),'volume_percentile':pct(vols,rows[-1]['volume']),'atr_percentile':pct(sorted(atrs),a) if a is not None else None}


def _scenario(direction,st,bos,liq,delta,vwap,profile,fvg,ob):
    scores={}
    continuation=0; reversal=0; expansion=0
    if direction=='LONG':
        continuation+=18 if st['state']=='HH_HL' else 0; continuation+=18 if bos['event']=='BOS_UP' else 0; continuation+=12 if vwap['position']=='ABOVE' else 0; continuation+=10 if delta['bias']=='BUY' else 0
        reversal+=25 if liq['sweep']=='SELL_SIDE_SWEEP_REJECTED' else 0; reversal+=20 if bos['event']=='CHOCH_UP' else 0; reversal+=12 if delta['bias']=='BUY' else 0; reversal+=8 if ob else 0
    else:
        continuation+=18 if st['state']=='LH_LL' else 0; continuation+=18 if bos['event']=='BOS_DOWN' else 0; continuation+=12 if vwap['position']=='BELOW' else 0; continuation+=10 if delta['bias']=='SELL' else 0
        reversal+=25 if liq['sweep']=='BUY_SIDE_SWEEP_REJECTED' else 0; reversal+=20 if bos['event']=='CHOCH_DOWN' else 0; reversal+=12 if delta['bias']=='SELL' else 0; reversal+=8 if ob else 0
    expansion+=15 if profile['location']!='VALUE_AREA' else 4; expansion+=12 if bos['event']!='NONE' else 0; expansion+=8 if (fvg['bullish'] if direction=='LONG' else fvg['bearish']) else 0
    scores['CONTINUATION']=min(100,40+continuation); scores['LIQUIDITY_REVERSAL']=min(100,35+reversal); scores['BREAKOUT_EXPANSION']=min(100,35+expansion)
    name=max(scores,key=scores.get); score=scores[name]
    return {'name':name,'score':score,'grade':'A' if score>=80 else 'B' if score>=68 else 'C' if score>=58 else 'WEAK','alternatives':scores}


def analyze(atlas,symbol):
    symbol=str(symbol or '').upper().replace('BINANCE:','')
    if symbol not in SUPPORTED:return {'ok':False,'error':'unsupported symbol','version':VERSION}
    frames={}
    errors={}
    for tf in ('1h','4h','6h','12h','1d'):
        try: frames[tf]=_klines(atlas,symbol,tf,220)
        except Exception as e: errors[tf]=str(e)
    if '4h' not in frames or '1h' not in frames:return {'ok':False,'error':'insufficient multi-timeframe data','errors':errors,'version':VERSION}
    states={tf:_bias(rows) for tf,rows in frames.items()}
    weights={'1d':1,'12h':2.5,'6h':3,'4h':3.5,'1h':1}; longw=sum(weights.get(tf,0) for tf,s in states.items() if s['bias']=='LONG'); shortw=sum(weights.get(tf,0) for tf,s in states.items() if s['bias']=='SHORT')
    direction='LONG' if longw>shortw else 'SHORT' if shortw>longw else None
    r4=frames['4h']; r1=frames['1h']; st=_structure(r4); bos=_bos_choch(r4,st); vwap=_anchored_vwap(r4,st); profile=_volume_profile(r4); delta=_volume_delta(r1); liq=_liquidity(r4); fvg=_fvg(r4); hist=_historical(r4)
    px=r1[-1]['close']; atr1=_atr(r1,14) or px*.005; atr4=_atr(r4,14) or px*.015
    evidence=[]; risks=[]; blockers=[]
    if not direction:blockers.append('NO_MTF_DIRECTIONAL_EDGE'); direction='LONG' if states['4h']['bias']=='LONG' else 'SHORT' if states['4h']['bias']=='SHORT' else 'NONE'
    if direction!='NONE':
        align=sum(1 for tf in ('4h','6h','12h','1d') if states.get(tf,{}).get('bias')==direction)
        if align>=3:evidence.append(f'MTF_ALIGNMENT_{align}/4')
        else:risks.append(f'WEAK_MTF_ALIGNMENT_{align}/4')
        if direction=='LONG' and st['state']=='HH_HL':evidence.append('4H_HH_HL_STRUCTURE')
        if direction=='SHORT' and st['state']=='LH_LL':evidence.append('4H_LH_LL_STRUCTURE')
        if bos['direction']==direction:evidence.append(bos['event'])
        if (direction=='LONG' and vwap['position']=='ABOVE') or (direction=='SHORT' and vwap['position']=='BELOW'):evidence.append('ANCHORED_VWAP_ALIGNED')
        else:risks.append('ANCHORED_VWAP_CONFLICT')
        if (direction=='LONG' and delta['bias']=='BUY') or (direction=='SHORT' and delta['bias']=='SELL'):evidence.append('DELTA_FLOW_ALIGNED')
        else:risks.append('DELTA_FLOW_CONFLICT')
        if (direction=='LONG' and delta['divergence']=='BEARISH_DIVERGENCE') or (direction=='SHORT' and delta['divergence']=='BULLISH_DIVERGENCE'):blockers.append('CVD_PRICE_DIVERGENCE_AGAINST_TRADE')
        if (direction=='LONG' and liq['sweep']=='SELL_SIDE_SWEEP_REJECTED') or (direction=='SHORT' and liq['sweep']=='BUY_SIDE_SWEEP_REJECTED'):evidence.append('LIQUIDITY_SWEEP_REVERSAL')
        if hist['price_percentile'] is not None and ((direction=='LONG' and hist['price_percentile']>=95) or (direction=='SHORT' and hist['price_percentile']<=5)):risks.append('HISTORICAL_PRICE_EXTENSION')
    ob=_order_block(r4,direction) if direction in ('LONG','SHORT') else None
    scenario=_scenario(direction,st,bos,liq,delta,vwap,profile,fvg,ob) if direction in ('LONG','SHORT') else {'name':'NONE','score':0,'grade':'WEAK','alternatives':{}}
    tech=50
    tech+=min(16,4*len(evidence)); tech-=min(20,5*len(risks)); tech-=min(30,10*len(blockers)); tech+=max(-8,min(12,(scenario['score']-60)*.25)); tech=max(0,min(100,round(tech,1)))
    if tech<52:blockers.append('TECHNICAL_SCORE_BELOW_52')
    if scenario['score']<60:blockers.append('SCENARIO_NOT_COHERENT')
    entry=px; stop=tp1=tp2=tp3=None; rr1=rr2=rr3=None; trigger='WAIT FOR VALID SETUP'; invalidation='NO_VALID_DIRECTION'
    if direction in ('LONG','SHORT'):
        sh=st.get('last_swing_high'); sl=st.get('last_swing_low')
        if direction=='LONG':
            preferred=max(px-0.35*atr1, (ob or {}).get('low',-math.inf)); entry=preferred if math.isfinite(preferred) else px; stop=(sl-0.12*atr1) if sl and sl<entry else entry-0.9*atr4; risk=entry-stop; candidates=[x for x in [profile.get('poc'),profile.get('vah'),liq.get('buy_side_target'),sh] if x and x>entry]; tp1=entry+1.5*risk; tp2=max(entry+2.2*risk,min(candidates) if candidates else entry+2.2*risk); tp3=entry+3*risk; trigger=f'1H bullish confirmation near {entry:.8g}'; invalidation=f'4H close below {stop:.8g}'
        else:
            preferred=min(px+0.35*atr1, (ob or {}).get('high',math.inf)); entry=preferred if math.isfinite(preferred) else px; stop=(sh+0.12*atr1) if sh and sh>entry else entry+0.9*atr4; risk=stop-entry; candidates=[x for x in [profile.get('poc'),profile.get('val'),liq.get('sell_side_target'),sl] if x and x<entry]; tp1=entry-1.5*risk; tp2=min(entry-2.2*risk,max(candidates) if candidates else entry-2.2*risk); tp3=entry-3*risk; trigger=f'1H bearish confirmation near {entry:.8g}'; invalidation=f'4H close above {stop:.8g}'
        if risk<=0:blockers.append('INVALID_RISK_GEOMETRY')
        else:
            rr1=abs(tp1-entry)/risk; rr2=abs(tp2-entry)/risk; rr3=abs(tp3-entry)/risk
            if rr2<1.8:blockers.append('RR_TP2_BELOW_1_8')
    last1=r1[-1]; prev1=r1[-2]; near=abs(px-entry)<=0.55*atr1 if direction in ('LONG','SHORT') else False
    directional=(last1['close']>last1['open']) if direction=='LONG' else (last1['close']<last1['open']) if direction=='SHORT' else False
    momentum=(last1['close']>prev1['high']) if direction=='LONG' else (last1['close']<prev1['low']) if direction=='SHORT' else False
    trigger_ready=bool(direction in ('LONG','SHORT') and near and directional and (momentum or abs(last1['close']-entry)<=.2*atr1))
    execution_state='READY_ON_TRIGGER' if trigger_ready and not blockers else 'WAIT_TRIGGER' if direction in ('LONG','SHORT') else 'WAIT'
    decision=direction if execution_state=='READY_ON_TRIGGER' and tech>=72 and scenario['score']>=68 else 'WAIT'
    return {'ok':True,'version':VERSION,'symbol':symbol,'generated_at_ms':int(time.time()*1000),'research_only':True,'live_execution':False,'horizon':'4-12H','decision':decision,'candidate_direction':direction,'execution_state':execution_state,'trigger_ready':trigger_ready,'technical_score':tech,'scenario':scenario,'mtf_states':states,'mtf_vote':{'long_weight':longw,'short_weight':shortw},'structure_4h':st,'bos_choch_4h':bos,'anchored_vwap_4h':vwap,'volume_profile_4h':profile,'delta_cvd_proxy_1h':delta,'liquidity_4h':liq,'order_block_4h':ob,'fvg_4h':fvg,'historical_context_4h':hist,'entry_plan':{'entry':entry,'stop_loss':stop,'tp1':tp1,'tp2':tp2,'tp3':tp3,'rr_tp1':rr1,'rr_tp2':rr2,'rr_tp3':rr3,'entry_trigger':trigger,'invalidation':invalidation,'expected_holding_hours':'4-12'},'evidence_for':evidence,'evidence_against':risks,'hard_blockers':sorted(set(blockers)),'decision_audit':{'technical_depth_pass':tech>=52,'scenario_coherence_pass':scenario['score']>=60,'rr_pass':rr2 is not None and rr2>=1.8,'trigger_pass':trigger_ready,'no_hard_blockers':not blockers,'final_ready':decision in ('LONG','SHORT')},'errors':errors}


def install(atlas):
    original_get=atlas.Handler.do_GET
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/deep-analysis/current':
            q=urllib.parse.parse_qs(u.query); symbol=(q.get('symbol') or ['BTCUSDT'])[0]
            try:return self._json(analyze(atlas,symbol))
            except Exception as e:return self._json({'ok':False,'error':str(e),'version':VERSION},500)
        return original_get(self)
    atlas.Handler.do_GET=do_GET
    atlas.RC10_1_DEEP_ANALYSIS_VERSION=VERSION
    atlas.rc10_1_deep_analyze=lambda symbol: analyze(atlas,symbol)
    return atlas
