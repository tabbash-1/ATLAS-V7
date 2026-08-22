#!/usr/bin/env python3
import json, os, threading, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer

import collector_server as atlas

OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY','').strip()
ATLAS_AI_MODEL=os.environ.get('ATLAS_AI_MODEL','gpt-5.6-terra').strip() or 'gpt-5.6-terra'
ATLAS_AI_MAX_BODY=max(32768,min(2_000_000,int(os.environ.get('ATLAS_AI_MAX_BODY','700000'))))

AI_INSTRUCTIONS='''You are the research reasoning layer inside ATLAS, a crypto market analysis system. Analyze only the structured evidence in the supplied ATLAS packet. Never invent prices, indicators, news, liquidity, smart-money data, or historical facts. Missing or conflicting evidence must reduce confidence and may require WAIT. This is research-only, never guaranteed profit or live execution. Return ONLY one valid JSON object with these keys: decision (LONG|SHORT|WAIT), confidence (0-100 integer), market_regime (string), thesis (short string), entry_zone (array of two numbers or null), invalidation (number or null), stop_loss (number or null), take_profit_1 (number or null), take_profit_2 (number or null), take_profit_3 (number or null), risk_reward (number or null), supporting_factors (array of short strings), opposing_factors (array of short strings), missing_data (array of short strings), no_trade_reason (string or null). Respect higher timeframes more than lower timeframes and prefer WAIT when evidence quality is insufficient.'''

def _extract_text(obj):
    if isinstance(obj.get('output_text'),str) and obj['output_text'].strip():
        return obj['output_text'].strip()
    parts=[]
    for item in obj.get('output') or []:
        if not isinstance(item,dict): continue
        for c in item.get('content') or []:
            if isinstance(c,dict) and c.get('type') in ('output_text','text') and isinstance(c.get('text'),str):
                parts.append(c['text'])
    return '\n'.join(parts).strip()

def _clean_json_text(text):
    t=(text or '').strip()
    if t.startswith('```'):
        t=t.strip('`').strip()
        if t.lower().startswith('json'): t=t[4:].strip()
    a=t.find('{'); b=t.rfind('}')
    return t[a:b+1] if a>=0 and b>a else t

def openai_analyze(packet):
    if not OPENAI_API_KEY:
        raise RuntimeError('OPENAI_API_KEY is not configured')
    body={
      'model':ATLAS_AI_MODEL,
      'instructions':AI_INSTRUCTIONS,
      'input':json.dumps(packet,separators=(',',':'),ensure_ascii=False),
      'max_output_tokens':1400
    }
    req=urllib.request.Request(
      'https://api.openai.com/v1/responses',
      data=json.dumps(body).encode('utf-8'),
      headers={'Authorization':f'Bearer {OPENAI_API_KEY}','Content-Type':'application/json','User-Agent':atlas.UA},
      method='POST'
    )
    with urllib.request.urlopen(req,timeout=45) as r:
        response=json.loads(r.read().decode('utf-8'))
    text=_extract_text(response)
    if not text: raise RuntimeError('AI returned no text output')
    thesis=json.loads(_clean_json_text(text))
    if not isinstance(thesis,dict): raise RuntimeError('AI output is not a JSON object')
    decision=str(thesis.get('decision') or 'WAIT').upper()
    if decision not in ('LONG','SHORT','WAIT'): decision='WAIT'
    thesis['decision']=decision
    try: thesis['confidence']=max(0,min(100,int(round(float(thesis.get('confidence',0))))))
    except: thesis['confidence']=0
    return thesis

class Handler(atlas.Handler):
    def do_POST(self):
        u=urllib.parse.urlparse(self.path)
        if u.path!='/api/ai/analyze':
            return super().do_POST()
        if not self._same_origin_write():
            return self._json({'ok':False,'error':'same-origin request required'},403)
        try:
            n=int(self.headers.get('Content-Length','0') or 0)
            if n<=0 or n>ATLAS_AI_MAX_BODY:
                return self._json({'ok':False,'error':'invalid analysis payload size'},413 if n>ATLAS_AI_MAX_BODY else 400)
            packet=json.loads(self.rfile.read(n).decode('utf-8') or '{}')
            if not isinstance(packet,dict) or packet.get('schema')!='ATLAS_AI_ANALYSIS_PACKET_V1':
                return self._json({'ok':False,'error':'invalid ATLAS AI packet'},400)
            thesis=openai_analyze(packet)
            return self._json({'ok':True,'provider':'OpenAI Responses API','model':ATLAS_AI_MODEL,'thesis':thesis,'research_only':True,'live_execution':False})
        except Exception as e:
            return self._json({'ok':False,'error':str(e),'fallback_expected':True,'research_only':True,'live_execution':False},503)

if __name__=='__main__':
    os.chdir(atlas.ROOT)
    threading.Thread(target=atlas.auto_loop,daemon=True).start()
    threading.Thread(target=atlas.news_loop,daemon=True).start()
    threading.Thread(target=atlas.cloud_forward_loop,daemon=True).start()
    port=int(os.environ.get('PORT','8080'))
    print('ATLAS V7 + AI gateway')
    print(f'AI model: {ATLAS_AI_MODEL} · key configured: {bool(OPENAI_API_KEY)}')
    print(f'Listening on port {port}')
    ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
