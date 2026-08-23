#!/usr/bin/env python3
import json, os, threading, time, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer

import collector_server as atlas

OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
ATLAS_AI_MODEL=os.environ.get('ATLAS_AI_MODEL','gpt-5.6-terra').strip() or 'gpt-5.6-terra'
ATLAS_AI_MAX_BODY=max(32768,min(2_000_000,int(os.environ.get('ATLAS_AI_MAX_BODY','700000'))))
AI_STATUS={'configured':bool(OPENAI_API_KEY),'model':ATLAS_AI_MODEL,'requests':0,'successes':0,'errors':0,'last_started_at':None,'last_success_at':None,'last_error_at':None,'last_error':None,'last_latency_ms':None}

AI_INSTRUCTIONS='''You are the research reasoning layer inside ATLAS, a crypto market analysis system. Analyze only the structured evidence in the supplied ATLAS packet. Never invent prices, indicators, news, liquidity, smart-money data, or historical facts. Missing or conflicting evidence must reduce confidence and may require WAIT. This is research-only, never guaranteed profit or live execution. Respect higher timeframes more than lower timeframes and prefer WAIT when evidence quality is insufficient.'''

THESIS_SCHEMA={
  'type':'object','additionalProperties':False,
  'properties':{
    'decision':{'type':'string','enum':['LONG','SHORT','WAIT']},
    'confidence':{'type':'integer','minimum':0,'maximum':100},
    'market_regime':{'type':'string'},'thesis':{'type':'string'},
    'entry_zone':{'anyOf':[{'type':'array','items':{'type':'number'},'minItems':2,'maxItems':2},{'type':'null'}]},
    'invalidation':{'type':['number','null']},'stop_loss':{'type':['number','null']},
    'take_profit_1':{'type':['number','null']},'take_profit_2':{'type':['number','null']},'take_profit_3':{'type':['number','null']},
    'risk_reward':{'type':['number','null']},
    'supporting_factors':{'type':'array','items':{'type':'string'}},
    'opposing_factors':{'type':'array','items':{'type':'string'}},
    'missing_data':{'type':'array','items':{'type':'string'}},
    'no_trade_reason':{'type':['string','null']}
  },
  'required':['decision','confidence','market_regime','thesis','entry_zone','invalidation','stop_loss','take_profit_1','take_profit_2','take_profit_3','risk_reward','supporting_factors','opposing_factors','missing_data','no_trade_reason']
}

def _extract_text(obj):
    if isinstance(obj.get('output_text'),str) and obj['output_text'].strip(): return obj['output_text'].strip()
    parts=[]
    for item in obj.get('output') or []:
        if not isinstance(item,dict): continue
        for c in item.get('content') or []:
            if isinstance(c,dict) and c.get('type') in ('output_text','text') and isinstance(c.get('text'),str): parts.append(c['text'])
    return '\n'.join(parts).strip()

def openai_analyze(packet):
    if not OPENAI_API_KEY: raise RuntimeError('OPENAI_API_KEY is not configured')
    started=time.time(); AI_STATUS['requests']+=1; AI_STATUS['last_started_at']=atlas.now_iso()
    body={
      'model':ATLAS_AI_MODEL,'instructions':AI_INSTRUCTIONS,
      'input':json.dumps(packet,separators=(',',':'),ensure_ascii=False),'max_output_tokens':1400,
      'text':{'format':{'type':'json_schema','name':'atlas_trade_thesis','strict':True,'schema':THESIS_SCHEMA}}
    }
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode('utf-8'),headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json','User-Agent':atlas.UA},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=45) as r: response=json.loads(r.read().decode('utf-8'))
        text=_extract_text(response)
        if not text: raise RuntimeError('AI returned no structured output')
        thesis=json.loads(text)
        if not isinstance(thesis,dict): raise RuntimeError('AI output is not a JSON object')
        AI_STATUS['successes']+=1; AI_STATUS['last_success_at']=atlas.now_iso(); AI_STATUS['last_error']=None
        return thesis
    except Exception as e:
        AI_STATUS['errors']+=1; AI_STATUS['last_error_at']=atlas.now_iso(); AI_STATUS['last_error']=str(e); raise
    finally: AI_STATUS['last_latency_ms']=round((time.time()-started)*1000)

def _bin(prefix,value,cuts=(55,70,85)):
    v=atlas.fnum(value)
    if v is None:return f'{prefix}_UNKNOWN'
    if v<cuts[0]:return f'{prefix}_LT_{cuts[0]}'
    if v<cuts[1]:return f'{prefix}_{cuts[0]}_{cuts[1]-1}'
    if v<cuts[2]:return f'{prefix}_{cuts[1]}_{cuts[2]-1}'
    return f'{prefix}_GE_{cuts[2]}'

def _score_sign_tag(prefix,obj):
    if not isinstance(obj,dict):return f'{prefix}_MISSING'
    v=atlas.fnum(obj.get('score'))
    if v is None:v=atlas.fnum(obj.get('experimental_score'))
    if v is None:return f'{prefix}_UNKNOWN'
    return f'{prefix}_POS' if v>10 else f'{prefix}_NEG' if v<-10 else f'{prefix}_NEUTRAL'

def _geom_tag(name,value):
    v=atlas.fnum(value)
    return f'GEOM_{name}={v:.12g}' if v is not None and v>0 else None

def _context_tags(packet,thesis):
    mt=packet.get('multi_timeframe') or {}; ev=packet.get('evidence') or {}; g=packet.get('trade_geometry') or {}; q=thesis.get('decision_quality') or {}
    tags=['ATLAS_AI_VALIDATION']
    htf=str(mt.get('higher_timeframe_bias') or 'UNKNOWN').upper().replace(' ','_')
    ltf=str(mt.get('entry_timing_bias') or 'UNKNOWN').upper().replace(' ','_')
    vol=str(g.get('volatility_regime') or 'UNKNOWN').upper().replace(' ','_')
    tags += [f'AI_HTF_{htf}',f'AI_LTF_{ltf}',f'AI_VOL_{vol}',_bin('AI_CONF',thesis.get('confidence'))]
    if q:
        tags += [_bin('AI_QUALITY',q.get('quality_score')),_bin('AI_READY',q.get('trade_readiness_score'))]
        tags.append(f"AI_GATE_{str(q.get('gate') or 'UNKNOWN').upper()}")
    rr=atlas.fnum(thesis.get('risk_reward'))
    tags.append('AI_RR_UNKNOWN' if rr is None else 'AI_RR_LT_1_5' if rr<1.5 else 'AI_RR_1_5_1_99' if rr<2 else 'AI_RR_2_2_99' if rr<3 else 'AI_RR_GE_3')
    tags += [_score_sign_tag('AI_FUT',ev.get('futures')),_score_sign_tag('AI_LIQ',ev.get('liquidity')),_score_sign_tag('AI_SM',ev.get('smart_money'))]
    for name,key in [('SL','stop_loss'),('TP1','take_profit_1'),('TP2','take_profit_2'),('TP3','take_profit_3')]:
        tag=_geom_tag(name,thesis.get(key))
        if tag: tags.append(tag)
    mc=ev.get('master_conviction')
    if isinstance(mc,dict):
        md=str(mc.get('decision') or mc.get('signal') or 'UNKNOWN').upper()
        tags.append(f'AI_MASTER_{md}')
    else:tags.append('AI_MASTER_MISSING')
    return sorted(set(tags))

def _validation_payload(packet,thesis,provider):
    decision=str(thesis.get('decision') or '').upper()
    if decision not in ('LONG','SHORT'): return None
    asset=packet.get('asset') or {}; symbol=str(asset.get('symbol') or '').upper().replace('BINANCE:','')
    if symbol not in atlas.ON_DEMAND_SYMBOLS: return None
    zone=thesis.get('entry_zone'); entry=None
    if isinstance(zone,list) and len(zone)>=2:
        vals=[atlas.fnum(x) for x in zone[:2]]
        if all(x is not None for x in vals): entry=sum(vals)/2
    if entry is None: entry=atlas.fnum((packet.get('trade_geometry') or {}).get('current_price'))
    if not entry: return None
    confidence=atlas.fnum(thesis.get('confidence'),0); rr=atlas.fnum(thesis.get('risk_reward'))
    return {'symbol':symbol,'direction':decision,'entry':entry,'champion_score':confidence,'final_score':confidence,
            'champion_take':True,'execution_decision':f'ATLAS_AI_{decision}','trade_plan_status':'PLAN_READY',
            'rr_tp2':rr,'regime':thesis.get('market_regime'),'playbook_primary':'ATLAS_AI_VALIDATION',
            'playbook_score':confidence,'playbook_all':_context_tags(packet,thesis),
            'auto_source':provider,'dedup_minutes':50}

def record_ai_validation(packet,thesis,provider):
    payload=_validation_payload(packet,thesis,provider)
    if not payload:return {'stored':False,'reason':'WAIT_OR_INVALID_GEOMETRY'}
    try:
        result=atlas.forward_observe(payload)
        if isinstance(result,dict) and 'stored' in result:return result
        return {'stored':True,'record':result}
    except Exception as e:return {'stored':False,'reason':'VALIDATION_STORE_ERROR','error':str(e)}

def _directional_return(row,horizon):
    v=atlas.fnum((row.get('forward_return_pct') or {}).get(str(horizon)))
    if v is None:return None
    return v if row.get('direction')=='LONG' else -v

def _sample_status(n):
    return 'ROBUSTNESS' if n>=200 else 'VALIDATION' if n>=100 else 'EARLY' if n>=30 else 'SMALL_SAMPLE'

def ai_attribution(symbol=None,horizon=24,min_n=5):
    rows=[r for r in atlas.forward_rows(symbol) if str(r.get('auto_source') or '').startswith('ATLAS_AI')]
    matured=[]
    for r in rows:
        dr=_directional_return(r,horizon)
        if dr is not None:matured.append((r,dr))
    baseline=[x[1] for x in matured]; base=atlas._seq_metrics(baseline)
    groups={}
    for r,dr in matured:
        for tag in r.get('playbook_all') or []:
            if not str(tag).startswith('AI_'):continue
            groups.setdefault(tag,[]).append(dr)
    factors=[]
    for tag,vals in groups.items():
        if len(vals)<min_n:continue
        m=atlas._seq_metrics(vals)
        delta=None
        if m.get('avg_return_pct') is not None and base.get('avg_return_pct') is not None:delta=m['avg_return_pct']-base['avg_return_pct']
        factors.append({'tag':tag,**m,'delta_vs_baseline_avg_pct':round(delta,4) if delta is not None else None})
    factors.sort(key=lambda x:(x['n'],x.get('delta_vs_baseline_avg_pct') if x.get('delta_vs_baseline_avg_pct') is not None else -999),reverse=True)
    strongest=sorted(factors,key=lambda x:(x.get('delta_vs_baseline_avg_pct') if x.get('delta_vs_baseline_avg_pct') is not None else -999),reverse=True)[:8]
    weakest=sorted(factors,key=lambda x:(x.get('delta_vs_baseline_avg_pct') if x.get('delta_vs_baseline_avg_pct') is not None else 999))[:8]
    return {'symbol':symbol,'horizon_h':horizon,'observations':len(rows),'matured':len(matured),'minimum_group_n':min_n,'baseline':base,'factors':factors,'strongest_associations':strongest,'weakest_associations':weakest,'method':'frozen decision-context tags grouped against directional forward returns; descriptive association only','research_only':True,'live_execution':False}

def ai_edge_breakdown(symbol=None,horizon=24):
    rows=[r for r in atlas.forward_rows(symbol) if str(r.get('auto_source') or '').startswith('ATLAS_AI')]
    matured=[]
    for r in rows:
        dr=_directional_return(r,horizon)
        if dr is not None:matured.append((r,dr))
    def grouped(keyfn):
        groups={}
        for r,dr in matured:
            k=str(keyfn(r) or 'UNKNOWN').strip() or 'UNKNOWN'
            groups.setdefault(k,[]).append(dr)
        out=[]
        for k,vals in groups.items():
            m=atlas._seq_metrics(vals)
            out.append({'group':k,'sample_status':_sample_status(len(vals)),**m})
        out.sort(key=lambda x:(x.get('n',0),x.get('avg_return_pct') if x.get('avg_return_pct') is not None else -999),reverse=True)
        return out
    return {'symbol':symbol,'horizon_h':horizon,'matured':len(matured),
            'by_direction':grouped(lambda r:r.get('direction')),
            'by_regime':grouped(lambda r:r.get('regime')),
            'sample_guard':{'small_sample_lt':30,'validation_ready_gte':100,'robustness_gte':200},
            'method':'AI-only directional forward returns grouped by frozen direction/regime at observation time',
            'research_only':True,'live_execution':False}

def _geometry_from_row(row):
    out={}
    for tag in row.get('playbook_all') or []:
        s=str(tag)
        if not s.startswith('GEOM_') or '=' not in s: continue
        k,v=s[5:].split('=',1); n=atlas.fnum(v)
        if n is not None: out[k]=n
    return {'stop_loss':out.get('SL'),'take_profit_1':out.get('TP1'),'take_profit_2':out.get('TP2'),'take_profit_3':out.get('TP3')}

def _fetch_5m_klines(symbol,start_ms,end_ms):
    qs=urllib.parse.urlencode({'symbol':symbol,'interval':'5m','startTime':int(start_ms),'endTime':int(end_ms),'limit':1000})
    errors=[]
    for host in ('https://api.binance.com','https://api1.binance.com','https://api2.binance.com'):
        try:
            req=urllib.request.Request(f'{host}/api/v3/klines?{qs}',headers={'User-Agent':atlas.UA,'Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r: return json.loads(r.read().decode('utf-8'))
        except Exception as e: errors.append(str(e))
    raise RuntimeError('kline providers failed: '+' | '.join(errors))

def _paper_path_row(row,horizon_h=24):
    geom=_geometry_from_row(row); sl=geom.get('stop_loss'); tp1=geom.get('take_profit_1')
    base={'symbol':row.get('symbol'),'direction':row.get('direction'),'entry':atlas.fnum(row.get('entry')),
          'captured_at':row.get('captured_at'),'captured_at_ms':row.get('captured_at_ms'),'score':row.get('champion_score'),
          'regime':row.get('regime'),'geometry':geom,'horizon_h':horizon_h}
    if not sl or not tp1:return {**base,'status':'PATH_UNAVAILABLE','reason':'candidate predates frozen SL/TP geometry or geometry was incomplete'}
    start=int(row.get('captured_at_ms') or 0); end=min(int(time.time()*1000),start+horizon_h*3600*1000)
    if not start:return {**base,'status':'PATH_UNAVAILABLE','reason':'missing captured_at_ms'}
    if end<=start:return {**base,'status':'OPEN','reason':'awaiting post-entry candles'}
    bars=_fetch_5m_klines(row.get('symbol'),start,end); direction=str(row.get('direction') or '').upper(); max_tp=0
    for b in bars:
        if not isinstance(b,list) or len(b)<5: continue
        ts=int(b[0]); high=atlas.fnum(b[2]); low=atlas.fnum(b[3])
        if high is None or low is None: continue
        if direction=='LONG':
            sl_hit=low<=sl; tp_hits=[i for i,k in enumerate(('take_profit_1','take_profit_2','take_profit_3'),1) if geom.get(k) and high>=geom[k]]
        else:
            sl_hit=high>=sl; tp_hits=[i for i,k in enumerate(('take_profit_1','take_profit_2','take_profit_3'),1) if geom.get(k) and low<=geom[k]]
        if tp_hits:max_tp=max(max_tp,max(tp_hits))
        tp1_hit=1 in tp_hits
        if sl_hit and tp1_hit:return {**base,'status':'AMBIGUOUS','reason':'SL and TP1 touched inside the same 5m candle; OHLC cannot prove intrabar order','event_at_ms':ts,'max_tp_reached':max_tp,'bars_checked':len(bars)}
        if sl_hit:return {**base,'status':'LOSS','reason':'SL touched before TP1','event_at_ms':ts,'max_tp_reached':max_tp,'bars_checked':len(bars)}
        if tp1_hit:return {**base,'status':'WIN','reason':'TP1 touched before SL','event_at_ms':ts,'max_tp_reached':max_tp,'bars_checked':len(bars)}
    aged=int(time.time()*1000)>=start+horizon_h*3600*1000
    return {**base,'status':'EXPIRED' if aged else 'OPEN','reason':'neither SL nor TP1 touched within evaluated path' if aged else 'neither SL nor TP1 touched yet','max_tp_reached':max_tp,'bars_checked':len(bars)}

def ai_paper_path(symbol=None,limit=20,horizon_h=24):
    rows=[r for r in atlas.forward_rows(symbol) if str(r.get('auto_source') or '').startswith('ATLAS_AI')]
    rows=sorted(rows,key=lambda r:int(r.get('captured_at_ms') or 0),reverse=True)[:max(1,min(int(limit),50))]
    out=[]
    for r in rows:
        try: out.append(_paper_path_row(r,horizon_h))
        except Exception as e: out.append({'symbol':r.get('symbol'),'direction':r.get('direction'),'captured_at':r.get('captured_at'),'status':'PATH_ERROR','reason':str(e)})
    eligible=[x for x in out if x.get('status') not in ('PATH_UNAVAILABLE','PATH_ERROR')]
    closed=[x for x in eligible if x.get('status') in ('WIN','LOSS','AMBIGUOUS','EXPIRED')]
    wins=sum(x.get('status')=='WIN' for x in closed); losses=sum(x.get('status')=='LOSS' for x in closed); denom=wins+losses
    return {'symbol':symbol,'horizon_h':horizon_h,'candidates':len(rows),'path_eligible':len(eligible),'closed':len(closed),'wins':wins,'losses':losses,
            'ambiguous':sum(x.get('status')=='AMBIGUOUS' for x in closed),'win_rate_ex_ambiguous_pct':round(wins/denom*100,2) if denom else None,'rows':out,
            'method':'5m Binance spot OHLC path; same-candle SL+TP1 is ambiguous; no exchange fill/slippage simulation','research_only':True,'live_execution':False}

class Handler(atlas.Handler):
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/ai/status':return self._json({'ok':True,'provider':'OpenAI Responses API','configured':AI_STATUS['configured'],'model':ATLAS_AI_MODEL,'structured_outputs':True,'status':dict(AI_STATUS),'research_only':True,'live_execution':False})
        if u.path=='/api/ai/validation':
            q=urllib.parse.parse_qs(u.query); sym=q.get('symbol',[None])[0]
            horizons={str(h):atlas.forward_stats(sym,h) for h in atlas.HORIZONS}; rows=[r for r in atlas.forward_rows(sym) if str(r.get('auto_source') or '').startswith('ATLAS_AI')]
            matured={str(h):sum(1 for r in rows if atlas.fnum((r.get('forward_return_pct') or {}).get(str(h))) is not None) for h in atlas.HORIZONS}
            n24=matured['24']; readiness='ROBUSTNESS_TEST_READY' if n24>=200 else 'VALIDATION_READY' if n24>=100 else 'EARLY_RESEARCH' if n24>=30 else 'NOT_READY'
            return self._json({'symbol':sym,'observations':len(rows),'matured':matured,'readiness':readiness,'horizons':horizons,'research_only':True,'live_execution':False})
        if u.path=='/api/ai/attribution':
            q=urllib.parse.parse_qs(u.query); sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0]); min_n=max(2,int(q.get('min_n',['5'])[0])); return self._json(ai_attribution(sym,horizon,min_n))
        if u.path=='/api/ai/edge-breakdown':
            q=urllib.parse.parse_qs(u.query); sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0])
            if horizon not in atlas.HORIZONS:return self._json({'ok':False,'error':'unsupported horizon'},400)
            return self._json(ai_edge_breakdown(sym,horizon))
        if u.path=='/api/ai/paper-path':
            q=urllib.parse.parse_qs(u.query); sym=q.get('symbol',[None])[0]; limit=int(q.get('limit',['20'])[0]); horizon=int(q.get('horizon',['24'])[0])
            if horizon not in atlas.HORIZONS:return self._json({'ok':False,'error':'unsupported horizon'},400)
            return self._json(ai_paper_path(sym,limit,horizon))
        return super().do_GET()

    def do_POST(self):
        u=urllib.parse.urlparse(self.path)
        if u.path!='/api/ai/analyze': return super().do_POST()
        if not self._same_origin_write(): return self._json({'ok':False,'error':'same-origin request required'},403)
        try:
            n=int(self.headers.get('Content-Length','0') or 0)
            if n<=0 or n>ATLAS_AI_MAX_BODY: return self._json({'ok':False,'error':'invalid analysis payload size'},413 if n>ATLAS_AI_MAX_BODY else 400)
            packet=json.loads(self.rfile.read(n).decode('utf-8') or '{}')
            if not isinstance(packet,dict) or packet.get('schema')!='ATLAS_AI_ANALYSIS_PACKET_V1': return self._json({'ok':False,'error':'invalid ATLAS AI packet'},400)
            thesis=openai_analyze(packet); validation=record_ai_validation(packet,thesis,'ATLAS_AI_OPENAI')
            return self._json({'ok':True,'provider':'OpenAI Responses API','model':ATLAS_AI_MODEL,'thesis':thesis,'validation':validation,'research_only':True,'live_execution':False})
        except Exception as e:return self._json({'ok':False,'error':str(e),'fallback_expected':True,'research_only':True,'live_execution':False},503)

if __name__=='__main__':
    os.chdir(atlas.ROOT); threading.Thread(target=atlas.auto_loop,daemon=True).start(); threading.Thread(target=atlas.news_loop,daemon=True).start(); threading.Thread(target=atlas.cloud_forward_loop,daemon=True).start()
    port=int(os.environ.get('PORT','8080')); print('ATLAS V7 + AI gateway'); print(f'AI model: {ATLAS_AI_MODEL} · key configured: {bool(OPENAI_API_KEY)}'); print(f'Listening on port {port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
