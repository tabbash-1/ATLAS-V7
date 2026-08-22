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
            'playbook_score':confidence,'playbook_all':['ATLAS_AI_VALIDATION'],
            'auto_source':provider,'dedup_minutes':50}

def record_ai_validation(packet,thesis,provider):
    payload=_validation_payload(packet,thesis,provider)
    if not payload:return {'stored':False,'reason':'WAIT_OR_INVALID_GEOMETRY'}
    try:
        result=atlas.forward_observe(payload)
        if isinstance(result,dict) and 'stored' in result:return result
        return {'stored':True,'record':result}
    except Exception as e:return {'stored':False,'reason':'VALIDATION_STORE_ERROR','error':str(e)}

class Handler(atlas.Handler):
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/ai/status':
            return self._json({'ok':True,'provider':'OpenAI Responses API','configured':AI_STATUS['configured'],'model':ATLAS_AI_MODEL,'structured_outputs':True,'status':dict(AI_STATUS),'research_only':True,'live_execution':False})
        if u.path=='/api/ai/validation':
            q=urllib.parse.parse_qs(u.query); sym=q.get('symbol',[None])[0]
            horizons={str(h):atlas.forward_stats(sym,h) for h in atlas.HORIZONS}
            rows=[r for r in atlas.forward_rows(sym) if str(r.get('auto_source') or '').startswith('ATLAS_AI')]
            matured={str(h):sum(1 for r in rows if atlas.fnum((r.get('forward_return_pct') or {}).get(str(h))) is not None) for h in atlas.HORIZONS}
            n24=matured['24']; readiness='ROBUSTNESS_TEST_READY' if n24>=200 else 'VALIDATION_READY' if n24>=100 else 'EARLY_RESEARCH' if n24>=30 else 'NOT_READY'
            return self._json({'symbol':sym,'observations':len(rows),'matured':matured,'readiness':readiness,'horizons':horizons,'research_only':True,'live_execution':False})
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
            thesis=openai_analyze(packet)
            validation=record_ai_validation(packet,thesis,'ATLAS_AI_OPENAI')
            return self._json({'ok':True,'provider':'OpenAI Responses API','model':ATLAS_AI_MODEL,'thesis':thesis,'validation':validation,'research_only':True,'live_execution':False})
        except Exception as e:
            return self._json({'ok':False,'error':str(e),'fallback_expected':True,'research_only':True,'live_execution':False},503)

if __name__=='__main__':
    os.chdir(atlas.ROOT)
    threading.Thread(target=atlas.auto_loop,daemon=True).start(); threading.Thread(target=atlas.news_loop,daemon=True).start(); threading.Thread(target=atlas.cloud_forward_loop,daemon=True).start()
    port=int(os.environ.get('PORT','8080'))
    print('ATLAS V7 + AI gateway'); print(f'AI model: {ATLAS_AI_MODEL} · key configured: {bool(OPENAI_API_KEY)}'); print(f'Listening on port {port}')
    ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
