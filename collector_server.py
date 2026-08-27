#!/usr/bin/env python3
import json, os, threading, time, urllib.parse, urllib.request, hashlib, re, xml.etree.ElementTree as ET, email.utils
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('ATLAS_DATA_DIR', str(ROOT/'data'))); DATA.mkdir(parents=True, exist_ok=True)
ARCHIVE=DATA/'smart_money_archive.jsonl'
CONFLUENCE_ARCHIVE=DATA/'confluence_memory.jsonl'
EVENT_ARCHIVE=DATA/'event_memory.jsonl'
FORWARD_ARCHIVE=DATA/'champion_challenger_forward.jsonl'
STAGE_STATE_FILE=DATA/'canary_stage_state.json'
ALERT_ARCHIVE=DATA/'confirmed_opportunity_alerts.jsonl'
ALERT_MIN_SCORE=float(os.environ.get('ATLAS_ALERT_MIN_SCORE','82'))
ALERT_MIN_RR=float(os.environ.get('ATLAS_ALERT_MIN_RR','2.0'))
ALERT_MIN_VOLUME_QUALITY=float(os.environ.get('ATLAS_ALERT_MIN_VOLUME_QUALITY','58'))
ALERT_COOLDOWN_MINUTES=max(30,int(os.environ.get('ATLAS_ALERT_COOLDOWN_MINUTES','240')))
SYMBOLS=('BTCUSDT','ETHUSDT')
ON_DEMAND_SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT')
INTERVAL_SECONDS=3600
UA=os.environ.get('ATLAS_HTTP_UA','ATLAS-Research/1.0 contact=research@example.invalid')
HORIZONS=(1,4,12,24)
CONFLUENCE_HORIZONS=(1,4,12,24)
EVENT_HORIZONS=(1,4,12,24)
NEWS_POLL_SECONDS=int(os.environ.get('ATLAS_NEWS_POLL_SECONDS','600'))
CLOUD_FORWARD_ENABLED=os.environ.get('ATLAS_CLOUD_FORWARD_ENABLED','1').lower() not in ('0','false','no')
CLOUD_FORWARD_INTERVAL_SECONDS=max(900,int(os.environ.get('ATLAS_CLOUD_FORWARD_INTERVAL_SECONDS','3600')))
CLOUD_FORWARD_MIN_SCORE=float(os.environ.get('ATLAS_CLOUD_FORWARD_MIN_SCORE','68'))
CLOUD_FORWARD_MAX_PER_CYCLE=max(1,min(7,int(os.environ.get('ATLAS_CLOUD_FORWARD_MAX_PER_CYCLE','3'))))
CLOUD_FORWARD_STATE={'enabled':CLOUD_FORWARD_ENABLED,'running':False,'cycles':0,'stored':0,'deduped':0,'errors':0,'last_started_at':None,'last_finished_at':None,'last_success_at':None,'last_error':None,'last_failed_stage':None,'last_candidates':[]}
STARTED_AT=time.time()
SMART_MONEY_STATE={'enabled':True,'cycles':0,'captures':0,'errors':0,'last_started_at':None,'last_success_at':None,'last_error':None}
MARKET_DATA_STATE={'spot':{'last_provider':None,'last_success_at':None,'last_error':None},
                   'futures':{'last_provider':'fapi.binance.com','last_success_at':None,'last_error':None}}
ARCHIVE_LOCK=threading.RLock()
NEWS_SOURCES=(
  {'id':'FED_MONETARY','name':'Federal Reserve - Monetary Policy','url':'https://www.federalreserve.gov/feeds/press_monetary.xml','tier':'PRIMARY','scope':'MARKET'},
  {'id':'BLS_CPI','name':'U.S. BLS - Consumer Price Index','url':'https://www.bls.gov/feed/cpi.rss','tier':'PRIMARY','scope':'MARKET'},
  {'id':'BLS_JOBS','name':'U.S. BLS - Employment Situation','url':'https://www.bls.gov/feed/empsit.rss','tier':'PRIMARY','scope':'MARKET'},
  {'id':'SEC_PRESS','name':'U.S. SEC - Crypto-relevant Press Releases','url':'https://www.sec.gov/news/pressreleases.rss','tier':'PRIMARY','scope':'MARKET',
   'filter_re':r'crypto|digital asset|bitcoin|ethereum|token|stablecoin|blockchain|exchange-traded|\betf\b|securities exchange|market structure'},
)

def now_iso(): return datetime.now(timezone.utc).isoformat()
def get_json(url, family=None):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json'})
    try:
      with urllib.request.urlopen(req,timeout=15) as r: obj=json.loads(r.read().decode())
      if family in MARKET_DATA_STATE:
        MARKET_DATA_STATE[family]['last_provider']=urllib.parse.urlparse(url).netloc
        MARKET_DATA_STATE[family]['last_success_at']=now_iso()
        MARKET_DATA_STATE[family]['last_error']=None
      return obj
    except Exception as e:
      if family in MARKET_DATA_STATE:
        MARKET_DATA_STATE[family]['last_error']=f'{urllib.parse.urlparse(url).netloc}: {e}'
      raise

def get_json_fallback(urls, family='spot'):
    errors=[]
    for url in urls:
      try:return get_json(url,family)
      except Exception as e:errors.append(f'{urllib.parse.urlparse(url).netloc}: {e}')
    if family in MARKET_DATA_STATE: MARKET_DATA_STATE[family]['last_error']=' | '.join(errors)
    raise RuntimeError('All market-data providers failed: '+' | '.join(errors))
def fnum(x,default=None):
    try:return float(x)
    except:return default

def read_all():
    out=[]
    if ARCHIVE.exists():
      with ARCHIVE.open() as f:
        for line in f:
          try: out.append(json.loads(line))
          except: pass
    return out





def normalize_text(s):
    s=re.sub(r'<[^>]+>',' ',str(s or ''))
    s=re.sub(r'\s+',' ',s).strip()
    return s

def event_fingerprint(title,url='',published=''):
    base='|'.join([normalize_text(title).lower(),str(url or '').strip().lower(),str(published or '')[:10]])
    return hashlib.sha256(base.encode('utf-8')).hexdigest()[:24]

def classify_event_py(title,summary=''):
    t=(str(title or '')+' '+str(summary or '')).lower()
    rules=[
      ('MACRO_RATE',r'interest rate|\bfomc\b|federal funds|monetary policy|rate decision'),
      ('MACRO_CPI',r'\bcpi\b|consumer price|inflation|\bppi\b'),
      ('MACRO_JOBS',r'payroll|unemployment|employment report|\bnfp\b|jobs report'),
      ('EXCHANGE_SECURITY',r'hack|exploit|breach|stolen|security incident'),
      ('EXCHANGE_OUTAGE',r'outage|withdrawal.{0,15}halt|trading.{0,15}halt'),
      ('ETF',r'\betf\b|exchange.traded fund'),
      ('REGULATION',r'regulat|\bsec\b|\bcftc\b|rulemaking|enforcement|lawsuit|approval|license'),
      ('TOKEN_UNLOCK',r'unlock|vesting'),
      ('LISTING',r'listing|listed on|delisting'),
      ('NETWORK_UPGRADE',r'upgrade|hard fork|mainnet|network update'),
      ('GEOPOLITICAL',r'war|missile|sanction|geopolit|military attack'),
    ]
    for k,pat in rules:
      if re.search(pat,t): return k
    return 'OTHER'

EVENT_IMPACT_PY={'MACRO_RATE':95,'MACRO_CPI':90,'MACRO_JOBS':80,'REGULATION':85,'ETF':85,'EXCHANGE_SECURITY':95,'EXCHANGE_OUTAGE':80,'TOKEN_UNLOCK':72,'LISTING':60,'NETWORK_UPGRADE':55,'GEOPOLITICAL':82,'OTHER':40}

def sentiment_py(title,summary=''):
    t=(str(title or '')+' '+str(summary or '')).lower(); s=0.0
    pos=('approval','approved','inflow','adoption','partnership','launch','successful','rate cut','cuts rates','lowers rates','record demand')
    neg=('hack','exploit','breach','ban','lawsuit','outage','halt','war','attack','sanction','rate hike','hikes rates','raises rates','rejection','rejected')
    for x in pos:
      if x in t:s+=.18
    for x in neg:
      if x in t:s-=.20
    return max(-1,min(1,s))

def score_event_py(title,summary='',source_tier='PRIMARY',confirmed=True,scope='MARKET'):
    typ=classify_event_py(title,summary); impact=EVENT_IMPACT_PY.get(typ,40)
    impact += 6 if source_tier=='PRIMARY' else 3 if source_tier=='TIER1' else -6 if source_tier=='UNKNOWN' else 0
    impact += 4 if confirmed else -12
    impact += 4 if scope=='MARKET' else 0
    impact=max(0,min(100,impact)); sent=sentiment_py(title,summary)
    direction='POSITIVE' if sent>=.18 else 'NEGATIVE' if sent<=-.18 else 'UNCLEAR'
    return {'event_type':typ,'impact_score':impact,'sentiment_score':round(sent,3),'direction':direction}

def parse_feed_xml(raw,source):
    root=ET.fromstring(raw)
    out=[]
    # RSS items
    for item in root.findall('.//item'):
      def tx(tag):
        el=item.find(tag); return normalize_text(el.text if el is not None else '')
      title=tx('title'); link=tx('link'); desc=tx('description'); pub=tx('pubDate')
      guid=tx('guid')
      if title: out.append({'title':title,'summary':desc,'url':link or guid,'published':pub})
    # Atom fallback
    ns={'a':'http://www.w3.org/2005/Atom'}
    for item in root.findall('.//a:entry',ns):
      title=normalize_text(item.findtext('a:title',default='',namespaces=ns))
      summary=normalize_text(item.findtext('a:summary',default='',namespaces=ns) or item.findtext('a:content',default='',namespaces=ns))
      updated=normalize_text(item.findtext('a:updated',default='',namespaces=ns))
      link=''
      le=item.find('a:link',ns)
      if le is not None: link=le.attrib.get('href','')
      if title: out.append({'title':title,'summary':summary,'url':link,'published':updated})
    return out

def fetch_feed(source):
    req=urllib.request.Request(source['url'],headers={'User-Agent':UA,'Accept':'application/rss+xml, application/atom+xml, application/xml, text/xml'})
    with urllib.request.urlopen(req,timeout=20) as r: raw=r.read()
    return parse_feed_xml(raw,source)

def dedup_event_exists(fp):
    return any(x.get('fingerprint')==fp for x in read_event_all())

def parse_published_ms(text):
    s=str(text or '').strip()
    if not s:return None
    try:
      dt=email.utils.parsedate_to_datetime(s)
      if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
      return int(dt.timestamp()*1000)
    except: pass
    try:
      dt=datetime.fromisoformat(s.replace('Z','+00:00'))
      if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
      return int(dt.timestamp()*1000)
    except:return None

def ingest_news_once(max_per_source=15):
    stored=[]; errors=[]
    for source in NEWS_SOURCES:
      try:
        entries=fetch_feed(source)
        if source.get('filter_re'):
          rx=re.compile(source['filter_re'],re.I); entries=[e for e in entries if rx.search((e.get('title') or '')+' '+(e.get('summary') or ''))]
        entries=entries[:max_per_source]
        for e in reversed(entries): # preserve source chronology where feeds are newest-first
          fp=event_fingerprint(e.get('title'),e.get('url'),e.get('published'))
          if dedup_event_exists(fp): continue
          scored=score_event_py(e.get('title'),e.get('summary'),source['tier'],True,source['scope'])
          payload={
            'symbol':'BTCUSDT','title':e.get('title'),'summary':e.get('summary'),'event_type':scored['event_type'],
            'impact_score':scored['impact_score'],'sentiment_score':scored['sentiment_score'],'direction':scored['direction'],
            'source':source['name'],'source_tier':source['tier'],'source_url':e.get('url'),'confirmed':True,'scope':source['scope'],
            'fingerprint':fp,'published_text':e.get('published'),'event_at_ms':parse_published_ms(e.get('published')) or int(time.time()*1000),'auto_ingested':True
          }
          result=event_observe(payload); stored.append(result.get('record'))
      except Exception as ex: errors.append({'source':source['id'],'error':str(ex)})
    return {'stored':len(stored),'records':stored,'errors':errors,'sources':len(NEWS_SOURCES),'shadow_mode':True,'research_only':True}

def _nearest_snapshot_before(symbol,target_ms,tolerance_ms=2*3600*1000):
    rows=[x for x in read_all() if x.get('symbol')==symbol and int(x.get('captured_at_ms',0))<=target_ms]
    rows.sort(key=lambda x:int(x.get('captured_at_ms',0)),reverse=True)
    return next((x for x in rows if target_ms-int(x.get('captured_at_ms',0))<=tolerance_ms),None)

def event_reaction_rows(symbol=None):
    rows=event_forward_rows(symbol)
    for r in rows:
      t=int(r.get('event_at_ms') or r.get('captured_at_ms',0)); sym=r.get('symbol')
      pre=_nearest_snapshot_before(sym,t)
      post=_nearest_snapshot_after(sym,t+3600*1000,90*60*1000)
      fr=r.get('forward_return_pct') or {}
      early=fnum(fr.get('1'))
      sent=fnum(r.get('sentiment_score'),0)
      reaction={'available':False,'label':'WAITING_FOR_FORWARD_SNAPSHOT'}
      if early is not None:
        expected=1 if sent>=.18 else -1 if sent<=-.18 else 0
        actual=1 if early>0 else -1 if early<0 else 0
        label='CONFIRMS_EVENT_DIRECTION' if expected and actual==expected else 'REJECTS_EVENT_DIRECTION' if expected and actual==-expected else 'AMBIGUOUS_REACTION'
        reaction={'available':True,'early_return_pct':early,'label':label}
        if pre and post:
          pt=fnum(pre.get('taker_buy_vol')); ps=fnum(pre.get('taker_sell_vol'))
          qt=fnum(post.get('taker_buy_vol')); qs=fnum(post.get('taker_sell_vol'))
          pre_total=(pt or 0)+(ps or 0); post_total=(qt or 0)+(qs or 0)
          reaction['taker_volume_ratio']=round(post_total/pre_total,3) if pre_total>0 else None
          reaction['oi_change_pre']=fnum(pre.get('oi_change_pct'))
          reaction['oi_change_post']=fnum(post.get('oi_change_pct'))
          reaction['funding_pre']=fnum(pre.get('funding_rate'))
          reaction['funding_post']=fnum(post.get('funding_rate'))
          reaction['book_imbalance_pre']=fnum(pre.get('orderbook_imbalance'))
          reaction['book_imbalance_post']=fnum(post.get('orderbook_imbalance'))
      r['reaction']=reaction
    return rows

def news_loop():
    # Warm delay avoids slowing boot/deploy.
    time.sleep(8)
    while True:
      try: ingest_news_once()
      except Exception as e: print('ATLAS news ingest error:',e)
      time.sleep(max(300,NEWS_POLL_SECONDS))

def read_event_all():
    out=[]
    if EVENT_ARCHIVE.exists():
      with EVENT_ARCHIVE.open() as f:
        for line in f:
          try: out.append(json.loads(line))
          except: pass
    return out

def latest_symbol_snapshot(symbol):
    rows=[x for x in read_all() if x.get('symbol')==symbol]
    return rows[-1] if rows else None

def event_observe(payload):
    symbol=str(payload.get('symbol') or 'BTCUSDT').upper().replace('BINANCE:','')
    title=str(payload.get('title') or '').strip()
    if not title: raise ValueError('title is required')
    nowms=int(time.time()*1000)
    event_ms=int(payload.get('event_at_ms') or nowms)
    snap=latest_symbol_snapshot(symbol)
    price=fnum(payload.get('price'))
    if price is None and snap: price=fnum(snap.get('mark_price') or snap.get('last_price'))
    rec={
      'schema':'ATLAS_EVENT_MEMORY_V1','captured_at':now_iso(),'captured_at_ms':nowms,
      'event_at_ms':event_ms,'symbol':symbol,'title':title,'summary':str(payload.get('summary') or '')[:2000],
      'event_type':str(payload.get('event_type') or payload.get('type') or 'OTHER').upper(),
      'impact_score':fnum(payload.get('impact_score')),'sentiment_score':fnum(payload.get('sentiment_score')),
      'direction':payload.get('direction'),'source':payload.get('source'),'source_tier':payload.get('source_tier'),
      'source_url':payload.get('source_url'),'confirmed':payload.get('confirmed'),'scope':payload.get('scope') or 'MARKET','fingerprint':payload.get('fingerprint'),'published_text':payload.get('published_text'),'auto_ingested':bool(payload.get('auto_ingested')),
      'actual':fnum(payload.get('actual')),'consensus':fnum(payload.get('consensus')),'previous':fnum(payload.get('previous')),'surprise_scale':fnum(payload.get('surprise_scale')),
      'normalized_surprise':fnum(payload.get('normalized_surprise')),'surprise_magnitude':fnum(payload.get('surprise_magnitude')),'surprise_risk_direction':payload.get('surprise_risk_direction'),
      'price_at_event':price,'research_only':True,'shadow_mode':True,'live_execution':False
    }
    # Keep futures/reaction context if supplied.
    for k in ('futures_score','futures_bias','funding_rate','oi_change_pct','taker_ratio','orderbook_imbalance',
              'relative_volume','volume_quality','regime','asset_return_pct','btc_return_pct'):
      if k in payload: rec[k]=payload.get(k)
    with EVENT_ARCHIVE.open('a') as f: f.write(json.dumps(rec,separators=(',',':'))+'\n')
    return {'stored':True,'record':rec}

def _nearest_snapshot_after(symbol,target_ms,tolerance_ms=90*60*1000):
    rows=[x for x in read_all() if x.get('symbol')==symbol]
    rows.sort(key=lambda x:int(x.get('captured_at_ms',0)))
    return next((x for x in rows if int(x.get('captured_at_ms',0))>=target_ms and int(x.get('captured_at_ms',0))<=target_ms+tolerance_ms),None)

def event_forward_rows(symbol=None):
    rows=read_event_all()
    if symbol: rows=[x for x in rows if x.get('symbol')==symbol]
    out=[]
    for x in rows:
      base=fnum(x.get('price_at_event')); t=int(x.get('event_at_ms') or x.get('captured_at_ms',0)); fr={}
      for h in EVENT_HORIZONS:
        cand=_nearest_snapshot_after(x.get('symbol'),t+h*3600*1000)
        px=fnum(cand.get('mark_price') or cand.get('last_price')) if cand else None
        fr[str(h)]=round((px/base-1)*100,5) if px is not None and base else None
      y=dict(x); y['forward_return_pct']=fr; out.append(y)
    return out


def economic_surprise_stats(symbol=None):
    rows=event_reaction_rows(symbol)
    groups={}
    for r in rows:
      if r.get('normalized_surprise') is None: continue
      key=r.get('event_type') or 'OTHER'
      g=groups.setdefault(key,{'event_type':key,'n':0,'confirm':0,'reject':0,'avg_abs_surprise':0.0,'avg_1h_return':0.0,'matured_1h':0})
      g['n']+=1; g['avg_abs_surprise']+=abs(fnum(r.get('normalized_surprise'),0) or 0)
      rx=r.get('reaction') or {}
      if rx.get('available'):
        g['matured_1h']+=1
        ret=fnum(rx.get('early_return_pct'))
        if ret is not None:g['avg_1h_return']+=ret
        risk=r.get('surprise_risk_direction')
        expected=1 if risk=='RISK_ON' else -1 if risk=='RISK_OFF' else 0
        if expected and ret is not None:
          actual=1 if ret>0 else -1 if ret<0 else 0
          if actual==expected:g['confirm']+=1
          elif actual==-expected:g['reject']+=1
    out=[]
    for g in groups.values():
      n=g['n']; m=g['matured_1h']
      g['avg_abs_surprise']=round(g['avg_abs_surprise']/n,4) if n else None
      g['avg_1h_return']=round(g['avg_1h_return']/m,4) if m else None
      denom=g['confirm']+g['reject']
      g['direction_confirm_rate_pct']=round(g['confirm']/denom*100,2) if denom else None
      out.append(g)
    return {'symbol':symbol,'groups':sorted(out,key=lambda x:x['n'],reverse=True),'shadow_mode':True,'research_only':True,'live_execution':False}

def event_stats(symbol=None):
    rows=event_forward_rows(symbol)
    groups={}
    for r in rows:
      key=r.get('event_type') or 'OTHER'
      g=groups.setdefault(key,{'event_type':key,'n':0,'horizons':{}})
      g['n']+=1
    for key,g in groups.items():
      subset=[r for r in rows if (r.get('event_type') or 'OTHER')==key]
      for h in EVENT_HORIZONS:
        vals=[fnum((r.get('forward_return_pct') or {}).get(str(h))) for r in subset]
        vals=[v for v in vals if v is not None]
        pos=[v for v in vals if v>0]
        neg=[v for v in vals if v<0]
        g['horizons'][str(h)]={
          'n':len(vals),
          'positive_rate_pct':round(len(pos)/len(vals)*100,2) if vals else None,
          'negative_rate_pct':round(len(neg)/len(vals)*100,2) if vals else None,
          'avg_return_pct':round(sum(vals)/len(vals),4) if vals else None,
          'avg_abs_move_pct':round(sum(abs(v) for v in vals)/len(vals),4) if vals else None
        }
    return {'symbol':symbol,'events':len(rows),'types':sorted(groups.values(),key=lambda x:x['n'],reverse=True),
            'shadow_mode':True,'research_only':True,'live_execution':False}

def read_confluence_all():
    out=[]
    if CONFLUENCE_ARCHIVE.exists():
      with CONFLUENCE_ARCHIVE.open() as f:
        for line in f:
          try: out.append(json.loads(line))
          except: pass
    return out

def confluence_observe(payload):
    symbol=str(payload.get('symbol') or '').upper().replace('BINANCE:','')
    if not symbol: raise ValueError('symbol is required')
    price=fnum(payload.get('price'))
    if not price or price<=0: raise ValueError('positive price is required')
    nowms=int(time.time()*1000)
    rows=[x for x in read_confluence_all() if x.get('symbol')==symbol]
    # Avoid duplicate research observations from repeated button clicks inside 45 minutes.
    if rows and nowms-int(rows[-1].get('captured_at_ms',0)) < 45*60*1000:
      return {'stored':False,'reason':'DEDUP_45M','record':rows[-1]}
    allowed={
      'signal','base_signal','confidence','gate_state','gate_reason','support_strength','support_distance_pct',
      'resistance_strength','resistance_distance_pct','relative_volume','volume_zscore','volume_trend_ratio',
      'volume_flow','volume_quality','breakout_score','breakout_state','breakdown_score','breakdown_state',
      'futures_score','futures_bias','futures_crowding','futures_squeeze','funding_rate','oi_change_pct','taker_ratio','orderbook_imbalance','futures_alignment',
      'liquidity_score','liquidity_long_pressure','liquidity_short_pressure',
      'anomaly_score','anomaly_level','anomaly_bias',
      'master_score','master_decision','final_score','final_decision',
      'trade_plan_status','trade_plan_quality','rr_tp1','rr_tp2','first_obstacle_strength','first_obstacle_type',
      'regime','relative_strength_score','opportunity_score'
    }
    rec={'schema':'ATLAS_CONFLUENCE_MEMORY_V1','captured_at':now_iso(),'captured_at_ms':nowms,'symbol':symbol,'price':price}
    for k in allowed:
      if k in payload: rec[k]=payload.get(k)
    rec['research_only']=True; rec['live_execution']=False
    with CONFLUENCE_ARCHIVE.open('a') as f: f.write(json.dumps(rec,separators=(',',':'))+'\n')
    return {'stored':True,'record':rec}

def confluence_forward_rows(symbol=None):
    rows=read_confluence_all()
    if symbol: rows=[x for x in rows if x.get('symbol')==symbol]
    bysym={}
    for x in read_confluence_all(): bysym.setdefault(x.get('symbol'),[]).append(x)
    for s in bysym: bysym[s].sort(key=lambda x:x.get('captured_at_ms',0))
    out=[]
    for x in rows:
      base=fnum(x.get('price')); t=int(x.get('captured_at_ms',0)); fr={}
      series=bysym.get(x.get('symbol'),[])
      for h in CONFLUENCE_HORIZONS:
        target=t+h*3600*1000
        cand=next((y for y in series if int(y.get('captured_at_ms',0))>=target and int(y.get('captured_at_ms',0))<=target+90*60*1000),None)
        fr[str(h)]=round((fnum(cand.get('price'))/base-1)*100,5) if cand and base and fnum(cand.get('price')) else None
      y=dict(x); y['forward_return_pct']=fr; out.append(y)
    return out

def _directional_return(row,h):
    r=fnum((row.get('forward_return_pct') or {}).get(str(h)))
    if r is None:return None
    sig=row.get('base_signal') or row.get('signal')
    if sig=='SELL': return -r
    if sig=='BUY': return r
    return None

def confluence_memory_stats(symbol):
    rows=confluence_forward_rows(symbol)
    matured={str(h):sum(1 for r in rows if (r.get('forward_return_pct') or {}).get(str(h)) is not None) for h in CONFLUENCE_HORIZONS}
    groups={}
    for r in rows:
      key=f"{r.get('gate_state','?')} | {r.get('gate_reason','?')}"
      g=groups.setdefault(key,{'setup':key,'n':0,'horizons':{}}); g['n']+=1
    for key,g in groups.items():
      subset=[r for r in rows if f"{r.get('gate_state','?')} | {r.get('gate_reason','?')}"==key]
      for h in CONFLUENCE_HORIZONS:
        vals=[_directional_return(r,h) for r in subset]; vals=[v for v in vals if v is not None]
        wins=[v for v in vals if v>0]
        g['horizons'][str(h)]={'n':len(vals),'hit_rate_pct':round(len(wins)/len(vals)*100,2) if vals else None,'avg_directional_return_pct':round(sum(vals)/len(vals),4) if vals else None}
    ranked=sorted(groups.values(),key=lambda g:(g['horizons'].get('24',{}).get('n') or 0),reverse=True)
    return {'symbol':symbol,'observations':len(rows),'matured':matured,'setups':ranked,'research_only':True,'live_execution':False}

def confluence_similar(symbol, current, limit=20):
    rows=confluence_forward_rows(symbol)
    features=['confidence','relative_volume','volume_trend_ratio','volume_quality','support_strength','support_distance_pct','resistance_strength','resistance_distance_pct','breakout_score','breakdown_score','futures_score','oi_change_pct','taker_ratio','orderbook_imbalance']
    scales={'confidence':25,'relative_volume':1.5,'volume_trend_ratio':0.6,'volume_quality':30,'support_strength':35,'support_distance_pct':5,'resistance_strength':35,'resistance_distance_pct':5,'breakout_score':35,'breakdown_score':35,'futures_score':45,'oi_change_pct':5,'taker_ratio':0.5,'orderbook_imbalance':0.5}
    scored=[]
    for r in rows:
      if not any((r.get('forward_return_pct') or {}).get(str(h)) is not None for h in CONFLUENCE_HORIZONS): continue
      ds=[]
      for f in features:
        a=fnum(current.get(f)); b=fnum(r.get(f))
        if a is not None and b is not None: ds.append(((a-b)/scales[f])**2)
      if len(ds)<4: continue
      dist=(sum(ds)/len(ds))**0.5
      # Penalize opposite base direction and different volume-flow regime.
      if current.get('base_signal') and r.get('base_signal')!=current.get('base_signal'): dist+=0.8
      if current.get('volume_flow') and r.get('volume_flow')!=current.get('volume_flow'): dist+=0.2
      scored.append((dist,r))
    picked=[r for _,r in sorted(scored,key=lambda x:x[0])[:max(1,min(limit,100))]]
    horizons={}
    for h in CONFLUENCE_HORIZONS:
      vals=[_directional_return(r,h) for r in picked]; vals=[v for v in vals if v is not None]
      horizons[str(h)]={'n':len(vals),'hit_rate_pct':round(sum(v>0 for v in vals)/len(vals)*100,2) if vals else None,'avg_directional_return_pct':round(sum(vals)/len(vals),4) if vals else None}
    return {'symbol':symbol,'matches':len(picked),'horizons':horizons,'research_only':True,'live_execution':False}


def _learn_num(row,key):
    return fnum(row.get(key))

def learning_tags(row):
    """Discrete context tags used for failure attribution. Research labels, not causal claims."""
    tags=[]
    sig=row.get('base_signal') or row.get('signal')
    vol=_learn_num(row,'volume_quality')
    rv=_learn_num(row,'relative_volume')
    res_s=_learn_num(row,'resistance_strength'); res_d=_learn_num(row,'resistance_distance_pct')
    sup_s=_learn_num(row,'support_strength'); sup_d=_learn_num(row,'support_distance_pct')
    br=_learn_num(row,'breakout_score'); bd=_learn_num(row,'breakdown_score')
    fs=_learn_num(row,'futures_score'); fund=_learn_num(row,'funding_rate'); oi=_learn_num(row,'oi_change_pct')
    taker=_learn_num(row,'taker_ratio'); book=_learn_num(row,'orderbook_imbalance')
    rr2=_learn_num(row,'rr_tp2'); an=_learn_num(row,'anomaly_score')
    liq=_learn_num(row,'liquidity_score'); rel=_learn_num(row,'relative_strength_score')
    if vol is not None:
      if vol<=38: tags.append('WEAK_VOLUME')
      if vol>=70: tags.append('STRONG_VOLUME')
    if rv is not None:
      if rv<0.8: tags.append('LOW_RELATIVE_VOLUME')
      if rv>=1.5: tags.append('VOLUME_EXPANSION')
    if sig=='BUY':
      if res_s is not None and res_d is not None and res_s>=75 and res_d<=1.5: tags.append('LONG_NEAR_STRONG_RESISTANCE')
      if br is not None and br<40: tags.append('LONG_LOW_BREAKOUT_QUALITY')
      if fs is not None and fs<=-25: tags.append('LONG_FUTURES_CONFLICT')
      if fund is not None and fund>=0.0005: tags.append('LONG_CROWDED_FUNDING')
      if taker is not None and taker<0.92: tags.append('LONG_TAKER_SELL_PRESSURE')
      if book is not None and book<-0.12: tags.append('LONG_ASK_BOOK_DOMINANT')
      if rel is not None and rel<=35: tags.append('LONG_RELATIVE_STRENGTH_WEAK')
    if sig=='SELL':
      if sup_s is not None and sup_d is not None and sup_s>=75 and sup_d<=1.5: tags.append('SHORT_NEAR_STRONG_SUPPORT')
      if bd is not None and bd<40: tags.append('SHORT_LOW_BREAKDOWN_QUALITY')
      if fs is not None and fs>=25: tags.append('SHORT_FUTURES_CONFLICT')
      if fund is not None and fund<=-0.0005: tags.append('SHORT_CROWDED_FUNDING')
      if taker is not None and taker>1.08: tags.append('SHORT_TAKER_BUY_PRESSURE')
      if book is not None and book>0.12: tags.append('SHORT_BID_BOOK_DOMINANT')
      if rel is not None and rel>=65: tags.append('SHORT_RELATIVE_STRENGTH_WEAK')
    if oi is not None and abs(oi)>=5: tags.append('OI_SHOCK')
    if rr2 is not None and rr2<1.8: tags.append('POOR_RR2')
    if an is not None and an>=70: tags.append('HIGH_ANOMALY')
    if liq is not None and liq<=35: tags.append('ADVERSE_LIQUIDITY')
    vf=row.get('volume_flow')
    if sig=='BUY' and vf=='BEARISH_DIVERGENCE': tags.append('LONG_BEARISH_VOLUME_DIVERGENCE')
    if sig=='SELL' and vf=='BULLISH_DIVERGENCE': tags.append('SHORT_BULLISH_VOLUME_DIVERGENCE')
    fc=str(row.get('futures_crowding') or '')
    sq=str(row.get('futures_squeeze') or '')
    if sig=='BUY' and ('LONG' in fc or sq=='LONG_SQUEEZE_RISK'): tags.append('LONG_CROWDING_OR_SQUEEZE_RISK')
    if sig=='SELL' and ('SHORT' in fc or sq=='SHORT_SQUEEZE_RISK'): tags.append('SHORT_CROWDING_OR_SQUEEZE_RISK')
    return sorted(set(tags))

def _learning_maturity_weight(n):
    if n<20:return 0.0
    if n<40:return 0.25
    if n<80:return 0.50
    if n<150:return 0.75
    return 1.0

def failure_learning(symbol=None,horizon=24):
    rows=confluence_forward_rows(symbol)
    matured=[]
    for r in rows:
      dr=_directional_return(r,horizon)
      if dr is not None and (r.get('base_signal') or r.get('signal')) in ('BUY','SELL'):
        y=dict(r);y['_directional_return']=dr;y['_tags']=learning_tags(r);matured.append(y)
    vals=[x['_directional_return'] for x in matured]
    baseline_hit=(sum(v>0 for v in vals)/len(vals)*100) if vals else None
    baseline_avg=(sum(vals)/len(vals)) if vals else None
    bytag={}
    for r in matured:
      for tag in r['_tags']:
        bytag.setdefault(tag,[]).append(r['_directional_return'])
    rules=[]
    for tag,v in bytag.items():
      n=len(v); w=_learning_maturity_weight(n)
      hit=sum(x>0 for x in v)/n*100 if n else None
      avg=sum(v)/n if n else None
      # Empirical-Bayes-like shrinkage toward the global baseline to reduce small-sample overreaction.
      shrink=n/(n+40.0)
      shrunk_hit=(baseline_hit+(hit-baseline_hit)*shrink) if baseline_hit is not None else hit
      shrunk_avg=(baseline_avg+(avg-baseline_avg)*shrink) if baseline_avg is not None else avg
      hit_drop=(baseline_hit-shrunk_hit) if baseline_hit is not None else 0
      avg_drop=(baseline_avg-shrunk_avg) if baseline_avg is not None else 0
      severity=max(0,hit_drop/4.0)+max(0,avg_drop*2.5)+max(0,-shrunk_avg*2.0)
      penalty=round(min(12.0,severity)*w,2)
      qualifies=bool(w>0 and penalty>=2 and ((hit_drop>=6) or (shrunk_avg is not None and shrunk_avg<0)))
      mid=max(1,n//2); h1=v[:mid]; h2=v[mid:]
      def half_stats(xs):
        if not xs:return {'n':0,'hit_rate_pct':None,'avg_return_pct':None}
        return {'n':len(xs),'hit_rate_pct':round(sum(x>0 for x in xs)/len(xs)*100,2),'avg_return_pct':round(sum(xs)/len(xs),4)}
      first=half_stats(h1); second=half_stats(h2)
      def half_bad(h):
        if not h.get('n'):return False
        return ((baseline_hit is not None and h.get('hit_rate_pct') is not None and h['hit_rate_pct']<=baseline_hit-5) or
                (h.get('avg_return_pct') is not None and h['avg_return_pct']<0))
      stable=bool(n>=40 and half_bad(first) and half_bad(second))
      promotion_ready=bool(n>=80 and w>=0.5 and qualifies and stable and penalty>=3)
      rules.append({
        'tag':tag,'n':n,'maturity_weight':w,'hit_rate_pct':round(hit,2),'avg_directional_return_pct':round(avg,4),
        'shrunk_hit_rate_pct':round(shrunk_hit,2),'shrunk_avg_return_pct':round(shrunk_avg,4),
        'baseline_hit_rate_pct':round(baseline_hit,2) if baseline_hit is not None else None,
        'baseline_avg_return_pct':round(baseline_avg,4) if baseline_avg is not None else None,
        'hit_drop_pct':round(hit_drop,2),'avg_drop_pct':round(avg_drop,4),'shadow_penalty':penalty,'qualifies':qualifies,
        'first_half':first,'second_half':second,'stable_across_halves':stable,'promotion_ready':promotion_ready
      })
    rules.sort(key=lambda x:(x['qualifies'],x['shadow_penalty'],x['n']),reverse=True)
    return {'symbol':symbol,'horizon_h':horizon,'matured_directional_setups':len(matured),
            'baseline':{'hit_rate_pct':round(baseline_hit,2) if baseline_hit is not None else None,'avg_directional_return_pct':round(baseline_avg,4) if baseline_avg is not None else None},
            'rules':rules,'qualified_rules':[x for x in rules if x['qualifies']],
            'promotion_candidates':[x for x in rules if x.get('promotion_ready')],
            'method':'sample-size gate + shrinkage + split-half stability; association not causation',
            'shadow_only':True,'research_only':True,'live_execution':False}


def _seq_metrics(vals):
    if not vals:return {'n':0,'hit_rate_pct':None,'avg_return_pct':None,'total_return_proxy':0,'max_drawdown_proxy':None}
    hit=sum(v>0 for v in vals)/len(vals)*100
    avg=sum(vals)/len(vals)
    equity=0.0; peak=0.0; maxdd=0.0
    for v in vals:
      equity+=v; peak=max(peak,equity); maxdd=max(maxdd,peak-equity)
    return {'n':len(vals),'hit_rate_pct':round(hit,2),'avg_return_pct':round(avg,4),
            'total_return_proxy':round(sum(vals),4),'max_drawdown_proxy':round(maxdd,4)}

def _discover_rules_from_rows(rows,baseline_vals):
    baseline_hit=sum(v>0 for v in baseline_vals)/len(baseline_vals)*100 if baseline_vals else None
    baseline_avg=sum(baseline_vals)/len(baseline_vals) if baseline_vals else None
    bytag={}
    for r in rows:
      for tag in r.get('_tags',[]): bytag.setdefault(tag,[]).append(r['_directional_return'])
    out=[]
    for tag,v in bytag.items():
      n=len(v); w=_learning_maturity_weight(n)
      hit=sum(x>0 for x in v)/n*100; avg=sum(v)/n
      shrink=n/(n+40.0)
      shrunk_hit=baseline_hit+(hit-baseline_hit)*shrink if baseline_hit is not None else hit
      shrunk_avg=baseline_avg+(avg-baseline_avg)*shrink if baseline_avg is not None else avg
      hit_drop=(baseline_hit-shrunk_hit) if baseline_hit is not None else 0
      avg_drop=(baseline_avg-shrunk_avg) if baseline_avg is not None else 0
      severity=max(0,hit_drop/4.0)+max(0,avg_drop*2.5)+max(0,-shrunk_avg*2.0)
      penalty=round(min(12.0,severity)*w,2)
      qualifies=bool(n>=40 and w>0 and penalty>=2 and ((hit_drop>=6) or shrunk_avg<0))
      out.append({'tag':tag,'discovery_n':n,'discovery_hit_rate_pct':round(hit,2),'discovery_avg_return_pct':round(avg,4),
                  'shadow_penalty':penalty,'qualifies':qualifies})
    return sorted(out,key=lambda x:(x['qualifies'],x['shadow_penalty'],x['discovery_n']),reverse=True)

def validate_learning_rules(symbol=None,horizon=24,discovery_frac=0.65):
    rows=confluence_forward_rows(symbol)
    matured=[]
    for r in rows:
      dr=_directional_return(r,horizon)
      if dr is not None and (r.get('base_signal') or r.get('signal')) in ('BUY','SELL'):
        y=dict(r); y['_directional_return']=dr; y['_tags']=learning_tags(r); matured.append(y)
    matured.sort(key=lambda x:int(x.get('captured_at_ms',0)))
    n=len(matured)
    if n<60:
      return {'symbol':symbol,'horizon_h':horizon,'matured':n,'status':'INSUFFICIENT_FOR_DISCOVERY_VALIDATION',
              'minimum_required':60,'promoted_rules':[],'rejected_rules':[],'shadow_only':True,'research_only':True,'live_execution':False}
    cut=max(40,min(n-20,int(n*discovery_frac)))
    discovery=matured[:cut]; validation=matured[cut:]
    dvals=[x['_directional_return'] for x in discovery]; vvals=[x['_directional_return'] for x in validation]
    discovered=_discover_rules_from_rows(discovery,dvals)
    candidates=[x for x in discovered if x['qualifies']]
    vbase=_seq_metrics(vvals)
    evaluated=[]
    for rule in candidates:
      tag=rule['tag']
      tagged=[x['_directional_return'] for x in validation if tag in x['_tags']]
      untagged=[x['_directional_return'] for x in validation if tag not in x['_tags']]
      tm=_seq_metrics(tagged); um=_seq_metrics(untagged)
      val_hit_drop=(vbase['hit_rate_pct']-tm['hit_rate_pct']) if tm['hit_rate_pct'] is not None and vbase['hit_rate_pct'] is not None else None
      val_avg_drop=(vbase['avg_return_pct']-tm['avg_return_pct']) if tm['avg_return_pct'] is not None and vbase['avg_return_pct'] is not None else None
      stable_bad=bool(tm['n']>=12 and ((val_hit_drop is not None and val_hit_drop>=5) or (tm['avg_return_pct'] is not None and tm['avg_return_pct']<0)))
      filter_improves=bool(um['n']>=15 and vbase['avg_return_pct'] is not None and um['avg_return_pct'] is not None and
                           um['avg_return_pct']>=vbase['avg_return_pct']+0.03 and
                           (um['max_drawdown_proxy'] is None or vbase['max_drawdown_proxy'] is None or um['max_drawdown_proxy']<=vbase['max_drawdown_proxy']*1.05))
      promoted=bool(stable_bad and filter_improves and tm['n']>=12)
      evaluated.append({**rule,'validation_tagged':tm,'validation_untagged':um,
                        'validation_baseline':vbase,'validation_hit_drop_pct':round(val_hit_drop,2) if val_hit_drop is not None else None,
                        'validation_avg_drop_pct':round(val_avg_drop,4) if val_avg_drop is not None else None,
                        'stable_bad_out_of_sample':stable_bad,'filter_improves_out_of_sample':filter_improves,
                        'promotion_status':'PROMOTED_SHADOW' if promoted else 'REJECTED_OR_WAITING','promoted':promoted})
    promoted=[x for x in evaluated if x['promoted']]
    rejected=[x for x in evaluated if not x['promoted']]
    # Portfolio-style filter using promoted tags together, evaluated only on validation.
    promoted_tags=set(x['tag'] for x in promoted)
    kept=[x['_directional_return'] for x in validation if not promoted_tags.intersection(x['_tags'])]
    removed=[x['_directional_return'] for x in validation if promoted_tags.intersection(x['_tags'])]
    combined={'baseline':vbase,'kept_after_promoted_filters':_seq_metrics(kept),'removed_by_filters':_seq_metrics(removed),
              'kept_fraction_pct':round(len(kept)/len(validation)*100,2) if validation else None}
    combined_improves=bool(promoted and len(kept)>=15 and combined['kept_after_promoted_filters']['avg_return_pct'] is not None and
                           vbase['avg_return_pct'] is not None and combined['kept_after_promoted_filters']['avg_return_pct']>vbase['avg_return_pct'])
    return {'symbol':symbol,'horizon_h':horizon,'matured':n,'discovery_n':len(discovery),'validation_n':len(validation),
            'split':'chronological','discovery_fraction':round(len(discovery)/n,3),'validation_baseline':vbase,
            'candidate_rules':len(candidates),'evaluated_rules':evaluated,'promoted_rules':promoted,'rejected_rules':rejected,
            'combined_validation':combined,'combined_improves_expectancy':combined_improves,
            'status':'PROMOTION_CANDIDATES_VALIDATED' if promoted else 'NO_RULE_PASSED_OUT_OF_SAMPLE',
            'promotion_effect':'SHADOW_ONLY_NOT_APPLIED_TO_FINAL_SCORE',
            'method':'chronological discovery/validation; rules discovered only on early sample and judged only on later sample',
            'shadow_only':True,'research_only':True,'live_execution':False}

def promoted_rule_assessment(symbol,current,horizon=24):
    v=validate_learning_rules(symbol,horizon)
    tags=set(learning_tags(current)); matches=[x for x in v.get('promoted_rules',[]) if x['tag'] in tags]
    # Still shadow: report what would happen, do not mutate scores.
    selected=sorted(matches,key=lambda x:x.get('shadow_penalty',0),reverse=True)[:3]
    would_reduce=round(min(15.0,sum(x.get('shadow_penalty',0) for x in selected)),2)
    return {'symbol':symbol,'current_tags':sorted(tags),'matched_promoted_rules':selected,'validated_shadow_penalty':would_reduce,
            'applied_to_final_score':False,'validation_status':v.get('status'),
            'shadow_only':True,'research_only':True,'live_execution':False}


def read_forward():
    out=[]
    if FORWARD_ARCHIVE.exists():
      with FORWARD_ARCHIVE.open() as f:
        for line in f:
          try: out.append(json.loads(line))
          except: pass
    return out

def _forward_write(row):
    with FORWARD_ARCHIVE.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')

def forward_observe(payload):
    symbol=str(payload.get('symbol') or 'BTCUSDT').upper().replace('BINANCE:','')
    if symbol not in ON_DEMAND_SYMBOLS: raise ValueError('Unsupported symbol')
    entry=fnum(payload.get('entry') or payload.get('price'))
    direction=str(payload.get('direction') or '').upper()
    if direction not in ('LONG','SHORT') or not entry: raise ValueError('direction LONG/SHORT and entry required')
    nowms=int(time.time()*1000)
    dedup_minutes=int(payload.get('dedup_minutes') or 50)
    incoming_execution=bool(payload.get('production_signal_qualified') and payload.get('execution_ready'))
    for old in reversed(read_forward()[-500:]):
      if old.get('symbol')==symbol and old.get('direction')==direction and nowms-int(old.get('captured_at_ms',0))<dedup_minutes*60*1000:
        # A legacy research observation must never swallow the first canonical
        # ACTIONABLE Production entry in the same window.
        if incoming_execution and not bool(old.get('production_signal_qualified') and old.get('execution_ready')):
          continue
        return {'stored':False,'reason':'DEDUP_WINDOW','existing_id':old.get('id'),'record':old}
    # Freeze the promoted-rule set at observation time. Future rule changes cannot rewrite history.
    validation=validate_learning_rules(symbol,24)
    promoted=validation.get('promoted_rules',[])
    tags=set(learning_tags(payload))
    matches=[x for x in promoted if x.get('tag') in tags]
    matched_tags=sorted(set(x.get('tag') for x in matches if x.get('tag')))
    challenger_penalty=round(min(15.0,sum(sorted([fnum(x.get('shadow_penalty'),0) for x in matches],reverse=True)[:3])),2)
    champion_score=fnum(payload.get('champion_score') or payload.get('final_score') or payload.get('master_score'),0)
    challenger_score=max(0,champion_score-challenger_penalty)
    champion_take=bool(payload.get('champion_take', champion_score>=60))
    threshold=fnum(payload.get('challenger_threshold'),60)
    challenger_take=bool(challenger_score>=threshold) if champion_take else False
    # Freeze adaptive allocation evidence at observation time; later learning cannot rewrite old sizing.
    fixed_risk=fnum(payload.get('fixed_risk_pct'),1.0)
    adaptive_mult=fnum(payload.get('adaptive_shadow_multiplier'))
    adaptive_risk=fnum(payload.get('adaptive_shadow_risk_pct'))
    if adaptive_mult is None:
      try:
        aa=adaptive_assess({**payload,'base_risk_pct':fixed_risk},24)
        adaptive_mult=fnum(aa.get('shadow_multiplier'),1.0)
        adaptive_risk=fnum(aa.get('shadow_suggested_risk_pct'),fixed_risk*adaptive_mult)
      except Exception:
        adaptive_mult=1.0;adaptive_risk=fixed_risk
    if adaptive_risk is None:adaptive_risk=fixed_risk*adaptive_mult

    # Controlled Canary assignment is deterministic and frozen at observation time.
    # Eligibility is based only on the Promotion Gate state available BEFORE this row is stored.
    canary_gate='NOT_ELIGIBLE'
    canary_feature=None
    try:
      pg=promotion_gate(24)
      if pg.get('adaptive',{}).get('status')=='ELIGIBLE_FOR_CONTROLLED_PROMOTION':
        canary_gate='ELIGIBLE'
        canary_feature='ADAPTIVE_SIZING'
    except Exception:
      pg=None
    stage_state=read_stage_state()
    stage_pct=int(stage_state.get('active_stage_pct',15))
    assignment_key=f"{symbol}|{direction}|{nowms}|{entry}|{canary_feature or 'NONE'}|STAGE{stage_pct}"
    bucket=int(hashlib.sha256(assignment_key.encode()).hexdigest()[:8],16)%100
    canary_arm='CANARY' if canary_gate=='ELIGIBLE' and bucket<stage_pct else 'CONTROL'
    canary_risk=adaptive_risk if canary_arm=='CANARY' and canary_feature=='ADAPTIVE_SIZING' else fixed_risk

    row={'schema':'ATLAS_FORWARD_V1','id':hashlib.sha256(f"{symbol}|{nowms}|{entry}".encode()).hexdigest()[:20],
         'captured_at':now_iso(),'captured_at_ms':nowms,'symbol':symbol,'direction':direction,'entry':entry,
         'champion_score':round(champion_score,3),'champion_take':champion_take,
         'challenger_score':round(challenger_score,3),'challenger_take':challenger_take,'challenger_threshold':threshold,
         'validated_shadow_penalty':challenger_penalty,'matched_promoted_tags':matched_tags,
         'playbook_primary':payload.get('playbook_primary'),'playbook_score':fnum(payload.get('playbook_score')),
         'playbook_all':payload.get('playbook_all') if isinstance(payload.get('playbook_all'),list) else [],
         'validation_status_at_entry':validation.get('status'),
         'auto_source':payload.get('auto_source') or 'MANUAL','opportunity_score':fnum(payload.get('opportunity_score')),
         'final_score':fnum(payload.get('final_score')),'execution_decision':payload.get('execution_decision'),
         'fixed_risk_pct':round(fixed_risk,4),
         'adaptive_shadow_multiplier':round(adaptive_mult,4),
         'adaptive_shadow_risk_pct':round(adaptive_risk,4),
         'canary_gate_at_entry':canary_gate,'canary_feature':canary_feature,
         'canary_arm':canary_arm,'canary_bucket':bucket,'canary_policy_pct':stage_pct,
         'canary_stage_pct_at_entry':stage_pct,'canary_stage_status_at_entry':stage_state.get('status'),
         'canary_shadow_risk_pct':round(canary_risk,4),
         'forward_return_pct':{}}
    # Store selected context for auditability.
    for k in ('trade_plan_status','rr_tp1','rr_tp2','stop_loss','tp1','tp2','signal_threshold',
              'production_signal_qualified','execution_ready','opportunity_state',
              'anomaly_score','futures_score','liquidity_score','regime','volume_quality','relative_volume'):
      if payload.get(k) is not None: row[k]=payload.get(k)
    _forward_write(row)
    return row

def forward_rows(symbol=None):
    rows=read_forward()
    if symbol: rows=[x for x in rows if x.get('symbol')==symbol]
    return rows

def _forward_matured(symbol=None,horizon=24):
    now_ms=int(time.time()*1000); hms=horizon*3600*1000
    out=[]
    rows=read_forward()
    if symbol: rows=[x for x in rows if x.get('symbol')==symbol]
    for r in rows:
      ret=fnum((r.get('forward_return_pct') or {}).get(str(horizon)))
      if ret is not None:
        x=dict(r);x['_market_return']=ret;out.append(x)
    return out

def forward_stats(symbol=None,horizon=24):
    rows=_forward_matured(symbol,horizon)
    def directional(r): return r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return']
    champ=[directional(r) for r in rows if r.get('champion_take')]
    chall=[directional(r) for r in rows if r.get('challenger_take')]
    avoided=[directional(r) for r in rows if r.get('champion_take') and not r.get('challenger_take')]
    cm=_seq_metrics(champ); xm=_seq_metrics(chall); am=_seq_metrics(avoided)
    delta_avg=(xm['avg_return_pct']-cm['avg_return_pct']) if xm['avg_return_pct'] is not None and cm['avg_return_pct'] is not None else None
    delta_hit=(xm['hit_rate_pct']-cm['hit_rate_pct']) if xm['hit_rate_pct'] is not None and cm['hit_rate_pct'] is not None else None
    verdict='COLLECTING'
    if len(rows)>=30 and len(chall)>=15:
      if delta_avg is not None and delta_avg>=0.05 and (xm['max_drawdown_proxy'] or 0)<=(cm['max_drawdown_proxy'] or 0)*1.05: verdict='CHALLENGER_LEADING'
      elif delta_avg is not None and delta_avg<=-0.05: verdict='CHAMPION_LEADING'
      else: verdict='NO_CLEAR_EDGE'
    return {'symbol':symbol,'horizon_h':horizon,'matured_observations':len(rows),
            'champion':cm,'challenger':xm,'avoided_by_challenger':am,
            'delta_avg_return_pct':round(delta_avg,4) if delta_avg is not None else None,
            'delta_hit_rate_pct':round(delta_hit,2) if delta_hit is not None else None,
            'verdict':verdict,'minimum_before_verdict':30,
            'challenger_changes_live_decisions':False,'research_only':True,'live_execution':False}


def playbook_forward_stats(symbol=None,horizon=24):
    rows=_forward_matured(symbol,horizon)
    groups={}
    for r in rows:
      pb=r.get('playbook_primary') or 'NO_PLAYBOOK'
      ret=r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return']
      groups.setdefault(pb,[]).append(ret)
    out=[]
    for pb,vals in groups.items():
      m=_seq_metrics(vals)
      pf=None
      gains=sum(v for v in vals if v>0); losses=-sum(v for v in vals if v<0)
      if losses>0: pf=gains/losses
      elif gains>0: pf=999
      out.append({'playbook':pb,**m,'profit_factor_proxy':round(pf,3) if pf is not None else None})
    out.sort(key=lambda x:(x['n'],x['avg_return_pct'] if x['avg_return_pct'] is not None else -999),reverse=True)
    return {'symbol':symbol,'horizon_h':horizon,'playbooks':out,'matured_observations':len(rows),
            'minimum_for_early_read':20,'minimum_for_stronger_read':50,
            'research_only':True,'live_execution':False}


def _pf(vals):
    gains=sum(v for v in vals if v>0); losses=-sum(v for v in vals if v<0)
    if losses>0:return round(gains/losses,3)
    if gains>0:return 999
    return None

def _group_forward(rows,keyfn):
    groups={}
    for r in rows:
      k=keyfn(r); ret=r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return']
      groups.setdefault(k,[]).append(ret)
    out=[]
    for k,vals in groups.items():
      m=_seq_metrics(vals)
      out.append({'group':k,**m,'profit_factor_proxy':_pf(vals)})
    out.sort(key=lambda x:(x['n'],x['avg_return_pct'] if x['avg_return_pct'] is not None else -999),reverse=True)
    return out


def _window_metrics(rows,start,end):
    xs=rows[start:end]
    vals=[]
    for r in xs:
      ret=fnum((r.get('forward_return_pct') or {}).get('24'))
      if ret is None:continue
      vals.append(ret if r.get('direction')=='LONG' else -ret)
    return _seq_metrics(vals)

def data_quality_report():
    forward=read_forward()
    smart=read_all()
    issues=[]
    nowms=int(time.time()*1000)
    # Forward archive quality
    missing_entry=sum(1 for r in forward if fnum(r.get('entry')) is None)
    missing_dir=sum(1 for r in forward if r.get('direction') not in ('LONG','SHORT'))
    dup_keys={}
    for r in forward:
      k=(r.get('symbol'),r.get('direction'),int(r.get('captured_at_ms',0))//(50*60*1000))
      dup_keys[k]=dup_keys.get(k,0)+1
    duplicate_buckets=sum(1 for v in dup_keys.values() if v>1)
    stale_smart=[]
    for s in ON_DEMAND_SYMBOLS:
      rows=[x for x in smart if x.get('symbol')==s]
      if rows:
        age=(nowms-int(rows[-1].get('captured_at_ms',0)))/3600000
        if age>6:stale_smart.append({'symbol':s,'age_h':round(age,2)})
    if missing_entry:issues.append(f'{missing_entry} forward rows missing entry')
    if missing_dir:issues.append(f'{missing_dir} forward rows missing direction')
    if duplicate_buckets:issues.append(f'{duplicate_buckets} duplicate 50m buckets')
    if stale_smart:issues.append('stale smart-money snapshots')
    provider_counts={}
    for r in smart:
      pp=r.get('futures_provider') or 'BINANCE_USDM_PUBLIC'
      provider_counts[pp]=provider_counts.get(pp,0)+1
    core_counts={s:sum(1 for r in smart if r.get('symbol')==s) for s in SYMBOLS}
    quality=100
    if len(forward)<30: issues.append(f'insufficient forward sample ({len(forward)}/30)'); quality-=35
    core_min=min(core_counts.values()) if core_counts else 0
    if core_min<7: issues.append('insufficient core smart-money coverage ('+', '.join(f'{s}:{core_counts.get(s,0)}/7' for s in SYMBOLS)+')'); quality-=25
    quality-=min(25,missing_entry*3)
    quality-=min(20,missing_dir*3)
    quality-=min(20,duplicate_buckets*2)
    quality-=min(20,len(stale_smart)*3)
    return {'quality_score':max(0,quality),'forward_rows':len(forward),'smart_money_rows':len(smart),
            'missing_entry':missing_entry,'missing_direction':missing_dir,'duplicate_buckets':duplicate_buckets,
            'stale_smart_money':stale_smart,'provider_counts':provider_counts,'core_symbol_counts':core_counts,'issues':issues,'status':'HEALTHY' if quality>=85 else 'WATCH' if quality>=65 else 'DEGRADED',
            'research_only':True,'live_execution':False}

def drift_report(horizon=24,recent_n=30,prior_n=60):
    rows=_forward_matured(None,horizon)
    rows.sort(key=lambda x:int(x.get('captured_at_ms',0)))
    if len(rows)<max(20,recent_n):
      return {'status':'COLLECTING','matured':len(rows),'minimum':max(20,recent_n),'alerts':[],'research_only':True,'live_execution':False}
    recent=rows[-recent_n:]
    prior=rows[-(recent_n+prior_n):-recent_n] if len(rows)>recent_n else []
    def vals(xs):
      return [(r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return']) for r in xs]
    rv=vals(recent);pv=vals(prior)
    rm=_seq_metrics(rv);pm=_seq_metrics(pv)
    alerts=[]
    avg_delta=(rm['avg_return_pct']-pm['avg_return_pct']) if pm['avg_return_pct'] is not None else None
    hit_delta=(rm['hit_rate_pct']-pm['hit_rate_pct']) if pm['hit_rate_pct'] is not None else None
    if avg_delta is not None and avg_delta<=-0.20:alerts.append('EXPECTANCY_DROPPED')
    if hit_delta is not None and hit_delta<=-15:alerts.append('HIT_RATE_DROPPED')
    if rm['max_drawdown_proxy'] is not None and pm['max_drawdown_proxy'] is not None and rm['max_drawdown_proxy']>pm['max_drawdown_proxy']*1.5 and rm['max_drawdown_proxy']>=1:alerts.append('DRAWDOWN_EXPANDED')
    # Source drift: browser vs cloud
    bysource={}
    for r in recent:
      src=r.get('auto_source') or 'MANUAL'
      bysource.setdefault(src,[]).append(r)
    source_metrics={k:_seq_metrics(vals(v)) for k,v in bysource.items()}
    # Playbook drift recent vs prior
    playbooks={}
    keys=set((r.get('playbook_primary') or 'NO_PLAYBOOK') for r in rows)
    for k in keys:
      a=[r for r in recent if (r.get('playbook_primary') or 'NO_PLAYBOOK')==k]
      b=[r for r in prior if (r.get('playbook_primary') or 'NO_PLAYBOOK')==k]
      am=_seq_metrics(vals(a));bm=_seq_metrics(vals(b))
      delta=(am['avg_return_pct']-bm['avg_return_pct']) if am['avg_return_pct'] is not None and bm['avg_return_pct'] is not None else None
      playbooks[k]={'recent':am,'prior':bm,'avg_delta_pct':round(delta,4) if delta is not None else None,
                    'drift':'NEGATIVE' if delta is not None and delta<=-.20 and am['n']>=8 and bm['n']>=8 else 'POSITIVE' if delta is not None and delta>=.20 and am['n']>=8 and bm['n']>=8 else 'STABLE_OR_UNCLEAR'}
      if playbooks[k]['drift']=='NEGATIVE':alerts.append(f'PLAYBOOK_DRIFT:{k}')
    status='EDGE_RISK' if alerts else 'STABLE'
    return {'status':status,'matured':len(rows),'recent_n':len(recent),'prior_n':len(prior),
            'recent':rm,'prior':pm,'avg_delta_pct':round(avg_delta,4) if avg_delta is not None else None,
            'hit_delta_pct':round(hit_delta,2) if hit_delta is not None else None,'source_metrics':source_metrics,
            'playbook_drift':playbooks,'alerts':sorted(set(alerts)),
            'recommendation':'PAUSE_PROMOTION_RESEARCH' if status=='EDGE_RISK' else 'CONTINUE_FORWARD_COLLECTION',
            'research_only':True,'live_execution':False}


def _adaptive_group_key(r):
    return (str(r.get('regime') or 'UNKNOWN'), str(r.get('playbook_primary') or 'NO_PLAYBOOK'))

def adaptive_edge_table(horizon=24,min_n=20):
    rows=_forward_matured(None,horizon)
    rows.sort(key=lambda x:int(x.get('captured_at_ms',0)))
    if not rows:
      return {'status':'COLLECTING','matured':0,'groups':[],'research_only':True,'live_execution':False}
    global_vals=[r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return'] for r in rows]
    global_avg=sum(global_vals)/len(global_vals) if global_vals else 0
    global_hit=sum(v>0 for v in global_vals)/len(global_vals)*100 if global_vals else 50
    groups={}
    for r in rows:
      groups.setdefault(_adaptive_group_key(r),[]).append(r)
    out=[]
    for (regime,pb),xs in groups.items():
      vals=[r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return'] for r in xs]
      n=len(vals); m=_seq_metrics(vals)
      # Recency view: last up to 20 observations in this group.
      recent_vals=vals[-min(20,n):]
      recent_avg=sum(recent_vals)/len(recent_vals) if recent_vals else None
      recent_hit=sum(v>0 for v in recent_vals)/len(recent_vals)*100 if recent_vals else None
      shrink=n/(n+40.0)
      shrunk_avg=global_avg+(m['avg_return_pct']-global_avg)*shrink if m['avg_return_pct'] is not None else global_avg
      shrunk_hit=global_hit+(m['hit_rate_pct']-global_hit)*shrink if m['hit_rate_pct'] is not None else global_hit
      # Blend lifetime and recent, but only when recent sample has some substance.
      rec_w=min(.45,len(recent_vals)/40.0)
      blended_avg=(1-rec_w)*shrunk_avg+rec_w*(recent_avg if recent_avg is not None else shrunk_avg)
      blended_hit=(1-rec_w)*shrunk_hit+rec_w*(recent_hit if recent_hit is not None else shrunk_hit)
      # Convert evidence into a conservative shadow allocation multiplier.
      edge_score=50
      edge_score+=max(-22,min(22,blended_avg*28))
      edge_score+=max(-16,min(16,(blended_hit-50)*.45))
      if m['profit_factor_proxy'] if isinstance(m,dict) and 'profit_factor_proxy' in m else False: pass
      if m['max_drawdown_proxy'] is not None and m['max_drawdown_proxy']>=4:edge_score-=8
      maturity=min(1,n/max(min_n,60))
      raw_mult=.55+(max(0,min(100,edge_score))/100)*.70
      multiplier=1+(raw_mult-1)*maturity
      if n<min_n:status='COLLECTING'
      elif blended_avg<0 or blended_hit<45:status='UNDERWEIGHT_SHADOW'
      elif blended_avg>=.15 and blended_hit>=55:status='OVERWEIGHT_SHADOW'
      else:status='NEUTRAL_SHADOW'
      multiplier=max(.50,min(1.25,multiplier))
      out.append({'regime':regime,'playbook':pb,'n':n,'hit_rate_pct':m['hit_rate_pct'],'avg_return_pct':m['avg_return_pct'],
                  'recent_n':len(recent_vals),'recent_hit_rate_pct':round(recent_hit,2) if recent_hit is not None else None,
                  'recent_avg_return_pct':round(recent_avg,4) if recent_avg is not None else None,
                  'shrunk_avg_return_pct':round(shrunk_avg,4),'blended_avg_return_pct':round(blended_avg,4),
                  'blended_hit_rate_pct':round(blended_hit,2),'edge_score':round(max(0,min(100,edge_score)),2),
                  'shadow_allocation_multiplier':round(multiplier,3),'status':status})
    out.sort(key=lambda x:(x['status']=='OVERWEIGHT_SHADOW',x['shadow_allocation_multiplier'],x['n']),reverse=True)
    return {'status':'READY' if len(rows)>=min_n else 'COLLECTING','matured':len(rows),
            'global':{'avg_return_pct':round(global_avg,4),'hit_rate_pct':round(global_hit,2)},
            'groups':out,'min_group_n':min_n,
            'allocation_is_applied':False,'research_only':True,'live_execution':False}

def adaptive_assess(payload,horizon=24):
    table=adaptive_edge_table(horizon)
    regime=str(payload.get('regime') or 'UNKNOWN')
    pb=str(payload.get('playbook_primary') or 'NO_PLAYBOOK')
    exact=next((x for x in table.get('groups',[]) if x['regime']==regime and x['playbook']==pb),None)
    # Fallback to regime-only evidence if exact combo is sparse/missing.
    regime_rows=[x for x in _forward_matured(None,horizon) if str(x.get('regime') or 'UNKNOWN')==regime]
    rvals=[x['_market_return'] if x.get('direction')=='LONG' else -x['_market_return'] for x in regime_rows]
    rm=_seq_metrics(rvals)
    fallback_mult=1.0
    if len(rvals)>=20 and rm['avg_return_pct'] is not None:
      fallback_mult=max(.70,min(1.15,1+rm['avg_return_pct']*.35))
    mult=exact['shadow_allocation_multiplier'] if exact and exact.get('n',0)>=table.get('min_group_n',20) else fallback_mult
    drift=drift_report(horizon,30,60)
    if drift.get('status')=='EDGE_RISK':
      mult=min(mult,.75)
    quality=data_quality_report()
    if quality.get('status')=='DEGRADED':
      mult=min(mult,.60)
    base_risk=fnum(payload.get('base_risk_pct'),1.0)
    suggested=round(base_risk*mult,4)
    return {'regime':regime,'playbook':pb,'matched_group':exact,'shadow_multiplier':round(mult,3),
            'base_risk_pct':base_risk,'shadow_suggested_risk_pct':suggested,
            'drift_status':drift.get('status'),'data_quality_status':quality.get('status'),
            'applied_to_portfolio_risk':False,'applied_to_final_score':False,
            'research_only':True,'live_execution':False}


def _weighted_path_metrics(rows,weight_key,horizon=24):
    vals=[]
    for r in rows:
      ret=fnum((r.get('forward_return_pct') or {}).get(str(horizon)))
      if ret is None:continue
      directional=ret if r.get('direction')=='LONG' else -ret
      w=fnum(r.get(weight_key),1.0)
      if weight_key=='adaptive_shadow_risk_pct' and r.get(weight_key) is None:
        fixed=fnum(r.get('fixed_risk_pct'),1.0); mult=fnum(r.get('adaptive_shadow_multiplier'),1.0); w=fixed*mult
      vals.append(directional*w)
    m=_seq_metrics(vals)
    m['profit_factor_proxy']=_pf(vals)
    return m

def adaptive_forward_comparison(horizon=24):
    rows=_forward_matured(None,horizon)
    usable=[r for r in rows if r.get('champion_take')]
    fixed=_weighted_path_metrics(usable,'fixed_risk_pct',horizon)
    adaptive=_weighted_path_metrics(usable,'adaptive_shadow_risk_pct',horizon)
    delta_avg=(adaptive['avg_return_pct']-fixed['avg_return_pct']) if adaptive['avg_return_pct'] is not None and fixed['avg_return_pct'] is not None else None
    dd_improvement=(fixed['max_drawdown_proxy']-adaptive['max_drawdown_proxy']) if fixed['max_drawdown_proxy'] is not None and adaptive['max_drawdown_proxy'] is not None else None
    # Simple risk-adjusted proxy: average weighted return / max drawdown, guarded against zero DD.
    fixed_ra=(fixed['avg_return_pct']/max(fixed['max_drawdown_proxy'],0.25)) if fixed['avg_return_pct'] is not None and fixed['max_drawdown_proxy'] is not None else None
    adaptive_ra=(adaptive['avg_return_pct']/max(adaptive['max_drawdown_proxy'],0.25)) if adaptive['avg_return_pct'] is not None and adaptive['max_drawdown_proxy'] is not None else None
    ra_delta=(adaptive_ra-fixed_ra) if adaptive_ra is not None and fixed_ra is not None else None
    verdict='COLLECTING'
    if len(usable)>=40:
      if delta_avg is not None and ra_delta is not None and delta_avg>0 and ra_delta>0 and (dd_improvement is None or dd_improvement>=-0.25):
        verdict='ADAPTIVE_LEADING_SHADOW'
      elif delta_avg is not None and delta_avg<-.03:
        verdict='FIXED_LEADING'
      else:
        verdict='NO_CLEAR_EDGE'
    return {'horizon_h':horizon,'usable_n':len(usable),'fixed':fixed,'adaptive_shadow':adaptive,
            'delta_avg_weighted_return_pct':round(delta_avg,4) if delta_avg is not None else None,
            'drawdown_improvement_proxy':round(dd_improvement,4) if dd_improvement is not None else None,
            'fixed_risk_adjusted_proxy':round(fixed_ra,4) if fixed_ra is not None else None,
            'adaptive_risk_adjusted_proxy':round(adaptive_ra,4) if adaptive_ra is not None else None,
            'risk_adjusted_delta':round(ra_delta,4) if ra_delta is not None else None,
            'verdict':verdict,'minimum_before_verdict':40,
            'adaptive_is_applied':False,'research_only':True,'live_execution':False}


STAGE_POLICY={
  'levels':[15,30,50],
  '15':{'min_canary':25,'min_control':75,'min_paired_delta':0.02,'min_ra_delta':0.03,'max_dd_worsening':0.10},
  '30':{'min_canary':35,'min_control':60,'min_paired_delta':0.02,'min_ra_delta':0.03,'max_dd_worsening':0.10},
  '50':{'min_canary':50,'min_control':50,'min_paired_delta':0.02,'min_ra_delta':0.03,'max_dd_worsening':0.10},
  'rollback_on_edge_risk':True,
  'rollback_on_degraded_data':True
}

def _default_stage_state():
    return {'active_stage_pct':15,'highest_passed_pct':0,'status':'STAGE_15_COLLECTING','transitions':[],'updated_at':now_iso()}

def read_stage_state():
    try:
      if STAGE_STATE_FILE.exists():
        x=json.loads(STAGE_STATE_FILE.read_text())
        if int(x.get('active_stage_pct',15)) in STAGE_POLICY['levels']:return x
    except Exception:pass
    return _default_stage_state()

def write_stage_state(state):
    state['updated_at']=now_iso()
    tmp=STAGE_STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state,separators=(',',':')))
    tmp.replace(STAGE_STATE_FILE)
    return state

CANARY_POLICY={
  'allocation_pct':15,
  'min_matured_canary':25,
  'min_matured_control':75,
  'min_paired_canary':25,
  'min_avg_improvement_pct':0.02,
  'min_risk_adjusted_delta':0.03,
  'max_dd_worsening':0.10
}

PROMOTION_POLICY={
  'min_adaptive_n':80,
  'min_delta_avg_pct':0.03,
  'min_risk_adjusted_delta':0.05,
  'max_dd_worsening':0.10,
  'min_rule_validation_n':20,
  'min_rule_discovery_n':60,
  'min_quality_score':85,
  'require_drift_stable':True,
  'require_multiple_regimes':True,
  'min_regime_count':2
}

def _gate_check(name,passed,value=None,threshold=None,detail=None):
    return {'name':name,'passed':bool(passed),'value':value,'threshold':threshold,'detail':detail}

def promotion_gate(horizon=24):
    adaptive=adaptive_forward_comparison(horizon)
    drift=drift_report(horizon,30,60)
    quality=data_quality_report()
    validation=validate_learning_rules(None,horizon)
    adaptive_table=adaptive_edge_table(horizon,20)

    checks=[]
    checks.append(_gate_check('DATA_QUALITY_HEALTHY',
      quality.get('quality_score',0)>=PROMOTION_POLICY['min_quality_score'] and quality.get('status')=='HEALTHY',
      quality.get('quality_score'),PROMOTION_POLICY['min_quality_score'],quality.get('status')))
    checks.append(_gate_check('NO_EDGE_DRIFT',
      drift.get('status')=='STABLE' if PROMOTION_POLICY['require_drift_stable'] else True,
      drift.get('status'),'STABLE',drift.get('alerts')))
    checks.append(_gate_check('ADAPTIVE_SAMPLE_SIZE',
      adaptive.get('usable_n',0)>=PROMOTION_POLICY['min_adaptive_n'],
      adaptive.get('usable_n'),PROMOTION_POLICY['min_adaptive_n']))
    checks.append(_gate_check('ADAPTIVE_EXPECTANCY_IMPROVES',
      adaptive.get('delta_avg_weighted_return_pct') is not None and adaptive.get('delta_avg_weighted_return_pct')>=PROMOTION_POLICY['min_delta_avg_pct'],
      adaptive.get('delta_avg_weighted_return_pct'),PROMOTION_POLICY['min_delta_avg_pct']))
    checks.append(_gate_check('ADAPTIVE_RISK_ADJUSTED_IMPROVES',
      adaptive.get('risk_adjusted_delta') is not None and adaptive.get('risk_adjusted_delta')>=PROMOTION_POLICY['min_risk_adjusted_delta'],
      adaptive.get('risk_adjusted_delta'),PROMOTION_POLICY['min_risk_adjusted_delta']))
    ddw=None
    if adaptive.get('fixed',{}).get('max_drawdown_proxy') is not None and adaptive.get('adaptive_shadow',{}).get('max_drawdown_proxy') is not None:
      ddw=adaptive['adaptive_shadow']['max_drawdown_proxy']-adaptive['fixed']['max_drawdown_proxy']
    checks.append(_gate_check('DRAWDOWN_NOT_MATERIALLY_WORSE',
      ddw is not None and ddw<=PROMOTION_POLICY['max_dd_worsening'],
      round(ddw,4) if ddw is not None else None,PROMOTION_POLICY['max_dd_worsening']))

    regimes=set()
    for g in adaptive_table.get('groups',[]):
      if g.get('n',0)>=20:regimes.add(g.get('regime'))
    checks.append(_gate_check('MULTI_REGIME_EVIDENCE',
      len(regimes)>=PROMOTION_POLICY['min_regime_count'] if PROMOTION_POLICY['require_multiple_regimes'] else True,
      len(regimes),PROMOTION_POLICY['min_regime_count'],sorted(regimes)))

    adaptive_pass=all(x['passed'] for x in checks)
    adaptive_status='ELIGIBLE_FOR_CONTROLLED_PROMOTION' if adaptive_pass else 'REMAIN_SHADOW'

    rule_rows=[]
    for r in validation.get('evaluated_rules',[]):
      rc=[]
      rc.append(_gate_check('DISCOVERY_N',r.get('discovery_n',0)>=PROMOTION_POLICY['min_rule_discovery_n'],r.get('discovery_n'),PROMOTION_POLICY['min_rule_discovery_n']))
      vn=(r.get('validation_tagged') or {}).get('n',0)
      rc.append(_gate_check('VALIDATION_N',vn>=PROMOTION_POLICY['min_rule_validation_n'],vn,PROMOTION_POLICY['min_rule_validation_n']))
      rc.append(_gate_check('OOS_STABLE_BAD',bool(r.get('stable_bad_out_of_sample')),r.get('stable_bad_out_of_sample'),True))
      rc.append(_gate_check('OOS_FILTER_IMPROVES',bool(r.get('filter_improves_out_of_sample')),r.get('filter_improves_out_of_sample'),True))
      rc.append(_gate_check('GLOBAL_DATA_QUALITY',quality.get('status')=='HEALTHY',quality.get('status'),'HEALTHY'))
      rc.append(_gate_check('GLOBAL_DRIFT_STABLE',drift.get('status')=='STABLE',drift.get('status'),'STABLE'))
      ok=all(x['passed'] for x in rc)
      rule_rows.append({'tag':r.get('tag'),'status':'ELIGIBLE_FOR_CONTROLLED_PROMOTION' if ok else 'REMAIN_SHADOW',
                        'checks':rc,'shadow_penalty':r.get('shadow_penalty'),'validation_tagged':r.get('validation_tagged'),
                        'discovery_n':r.get('discovery_n')})
    eligible_rules=[x for x in rule_rows if x['status']=='ELIGIBLE_FOR_CONTROLLED_PROMOTION']

    overall='PROMOTION_ELIGIBLE' if adaptive_pass or eligible_rules else 'NO_PROMOTION'
    return {'policy':PROMOTION_POLICY,'overall_status':overall,
            'adaptive':{'status':adaptive_status,'checks':checks,'forward_comparison':adaptive},
            'rules':rule_rows,'eligible_rules':eligible_rules,
            'data_quality':quality,'drift':drift,
            'automatic_activation':False,
            'next_step_if_eligible':'CONTROLLED_CANARY_ONLY',
            'research_only':True,'live_execution':False}



def _stage_cohort_report(stage_pct,horizon=24):
    rows=[r for r in _forward_matured(None,horizon)
          if r.get('champion_take') and r.get('canary_gate_at_entry')=='ELIGIBLE'
          and int(r.get('canary_stage_pct_at_entry') or r.get('canary_policy_pct') or 15)==int(stage_pct)]
    control=[r for r in rows if r.get('canary_arm')=='CONTROL']
    canary=[r for r in rows if r.get('canary_arm')=='CANARY']
    def weighted(xs,field):
      vals=[]
      for r in xs:
        ret=fnum((r.get('forward_return_pct') or {}).get(str(horizon)))
        if ret is None:continue
        d=ret if r.get('direction')=='LONG' else -ret
        vals.append(d*fnum(r.get(field),1.0))
      m=_seq_metrics(vals);m['profit_factor_proxy']=_pf(vals);return m
    ctrl=weighted(control,'fixed_risk_pct')
    can=weighted(canary,'canary_shadow_risk_pct')
    fixed_cf=weighted(canary,'fixed_risk_pct')
    pd=(can['avg_return_pct']-fixed_cf['avg_return_pct']) if can['avg_return_pct'] is not None and fixed_cf['avg_return_pct'] is not None else None
    def ra(m):
      if m.get('avg_return_pct') is None or m.get('max_drawdown_proxy') is None:return None
      return m['avg_return_pct']/max(m['max_drawdown_proxy'],.25)
    cra=ra(can);fra=ra(fixed_cf)
    rad=(cra-fra) if cra is not None and fra is not None else None
    dd=(can['max_drawdown_proxy']-fixed_cf['max_drawdown_proxy']) if can.get('max_drawdown_proxy') is not None and fixed_cf.get('max_drawdown_proxy') is not None else None
    pol=STAGE_POLICY[str(int(stage_pct))]
    enough=len(canary)>=pol['min_canary'] and len(control)>=pol['min_control']
    verdict='COLLECTING'
    if enough:
      if pd is not None and rad is not None and pd>=pol['min_paired_delta'] and rad>=pol['min_ra_delta'] and (dd is None or dd<=pol['max_dd_worsening']):
        verdict='PASS'
      elif pd is not None and pd<=-pol['min_paired_delta']:
        verdict='FAIL'
      else:verdict='INCONCLUSIVE'
    return {'stage_pct':int(stage_pct),'eligible_rows':len(rows),'control_n':len(control),'canary_n':len(canary),
            'observed_canary_pct':round(len(canary)/len(rows)*100,2) if rows else None,
            'control_fixed':ctrl,'canary_adaptive':can,'canary_fixed_counterfactual':fixed_cf,
            'paired_delta_avg_pct':round(pd,4) if pd is not None else None,
            'paired_risk_adjusted_delta':round(rad,4) if rad is not None else None,
            'paired_dd_worsening':round(dd,4) if dd is not None else None,
            'policy':pol,'verdict':verdict}

def stage_expansion_report(horizon=24,apply_transition=False):
    state=read_stage_state()
    active=int(state.get('active_stage_pct',15))
    reports={str(x):_stage_cohort_report(x,horizon) for x in STAGE_POLICY['levels']}
    drift=drift_report(horizon,30,60);quality=data_quality_report()
    current=reports[str(active)]
    recommended=active;action='HOLD'
    safety_hold=(drift.get('status')=='EDGE_RISK' or quality.get('status')=='DEGRADED')
    levels=STAGE_POLICY['levels'];i=levels.index(active)
    if safety_hold:
      if i>0:
        recommended=levels[i-1];action='ROLLBACK'
      else:action='HOLD_SAFETY'
    elif current['verdict']=='FAIL':
      if i>0:recommended=levels[i-1];action='ROLLBACK'
      else:action='HOLD_FAILED_STAGE_15'
    elif current['verdict']=='PASS':
      if i<len(levels)-1:
        recommended=levels[i+1];action='EXPAND'
      else:
        action='HOLD_AT_MAX_SHADOW'
    elif current['verdict']=='INCONCLUSIVE':action='HOLD_INCONCLUSIVE'
    else:action='COLLECT'

    transitioned=False
    if apply_transition and recommended!=active:
      old=active
      state['active_stage_pct']=recommended
      if action=='EXPAND':state['highest_passed_pct']=max(int(state.get('highest_passed_pct',0)),old)
      state['status']=f'STAGE_{recommended}_ACTIVE_AFTER_{action}'
      state.setdefault('transitions',[]).append({'at':now_iso(),'from':old,'to':recommended,'action':action,
                                                 'trigger_verdict':current['verdict'],'drift':drift.get('status'),'quality':quality.get('status')})
      write_stage_state(state);transitioned=True
    elif apply_transition:
      state['status']=f'STAGE_{active}_{action}'
      write_stage_state(state)

    return {'state':state,'active_stage_pct':active if not transitioned else recommended,
            'current_stage_report':reports[str(active)],'stage_reports':reports,
            'recommended_stage_pct':recommended,'recommended_action':action,'transition_applied':transitioned,
            'safety_hold':safety_hold,'drift_status':drift.get('status'),'data_quality_status':quality.get('status'),
            'automatic_shadow_transition_enabled':True,'live_activation':False,'research_only':True,'live_execution':False}

def canary_forward_report(horizon=24):
    rows=[r for r in _forward_matured(None,horizon) if r.get('champion_take') and r.get('canary_gate_at_entry')=='ELIGIBLE']
    control=[r for r in rows if r.get('canary_arm')=='CONTROL']
    canary=[r for r in rows if r.get('canary_arm')=='CANARY']

    def weighted(xs,weight_field):
      vals=[]
      for r in xs:
        ret=fnum((r.get('forward_return_pct') or {}).get(str(horizon)))
        if ret is None:continue
        directional=ret if r.get('direction')=='LONG' else -ret
        w=fnum(r.get(weight_field),1.0)
        vals.append(directional*w)
      m=_seq_metrics(vals);m['profit_factor_proxy']=_pf(vals)
      return m

    control_fixed=weighted(control,'fixed_risk_pct')
    canary_applied=weighted(canary,'canary_shadow_risk_pct')
    canary_fixed_counterfactual=weighted(canary,'fixed_risk_pct')

    cohort_delta=None
    if canary_applied.get('avg_return_pct') is not None and control_fixed.get('avg_return_pct') is not None:
      cohort_delta=canary_applied['avg_return_pct']-control_fixed['avg_return_pct']

    paired_delta=None
    if canary_applied.get('avg_return_pct') is not None and canary_fixed_counterfactual.get('avg_return_pct') is not None:
      paired_delta=canary_applied['avg_return_pct']-canary_fixed_counterfactual['avg_return_pct']

    def ra(m):
      if m.get('avg_return_pct') is None or m.get('max_drawdown_proxy') is None:return None
      return m['avg_return_pct']/max(m['max_drawdown_proxy'],0.25)

    control_ra=ra(control_fixed);canary_ra=ra(canary_applied);paired_fixed_ra=ra(canary_fixed_counterfactual)
    cohort_ra_delta=(canary_ra-control_ra) if canary_ra is not None and control_ra is not None else None
    paired_ra_delta=(canary_ra-paired_fixed_ra) if canary_ra is not None and paired_fixed_ra is not None else None
    dd_worse=None
    if canary_applied.get('max_drawdown_proxy') is not None and canary_fixed_counterfactual.get('max_drawdown_proxy') is not None:
      dd_worse=canary_applied['max_drawdown_proxy']-canary_fixed_counterfactual['max_drawdown_proxy']

    enough=bool(len(canary)>=CANARY_POLICY['min_matured_canary'] and len(control)>=CANARY_POLICY['min_matured_control'])
    paired_enough=bool(len(canary)>=CANARY_POLICY['min_paired_canary'])
    verdict='COLLECTING'
    if enough and paired_enough:
      if (paired_delta is not None and paired_delta>=CANARY_POLICY['min_avg_improvement_pct'] and
          paired_ra_delta is not None and paired_ra_delta>=CANARY_POLICY['min_risk_adjusted_delta'] and
          (dd_worse is None or dd_worse<=CANARY_POLICY['max_dd_worsening'])):
        verdict='CANARY_PASS'
      elif paired_delta is not None and paired_delta<=-CANARY_POLICY['min_avg_improvement_pct']:
        verdict='CANARY_FAIL'
      else:
        verdict='CANARY_INCONCLUSIVE'

    # Safety state is still advisory: no live feature activation.
    drift=drift_report(horizon,30,60)
    quality=data_quality_report()
    if drift.get('status')=='EDGE_RISK' or quality.get('status')=='DEGRADED':
      if verdict=='CANARY_PASS': verdict='CANARY_PASS_BUT_SAFETY_HOLD'

    return {
      'policy':CANARY_POLICY,'eligible_rows':len(rows),'control_n':len(control),'canary_n':len(canary),
      'observed_canary_share_pct':round(len(canary)/len(rows)*100,2) if rows else None,
      'control_fixed':control_fixed,'canary_applied_shadow':canary_applied,
      'canary_fixed_counterfactual':canary_fixed_counterfactual,
      'cohort_delta_avg_pct':round(cohort_delta,4) if cohort_delta is not None else None,
      'paired_delta_avg_pct':round(paired_delta,4) if paired_delta is not None else None,
      'cohort_risk_adjusted_delta':round(cohort_ra_delta,4) if cohort_ra_delta is not None else None,
      'paired_risk_adjusted_delta':round(paired_ra_delta,4) if paired_ra_delta is not None else None,
      'paired_drawdown_worsening':round(dd_worse,4) if dd_worse is not None else None,
      'verdict':verdict,'drift_status':drift.get('status'),'data_quality_status':quality.get('status'),
      'automatic_expansion':False,'automatic_activation':False,
      'next_step_if_pass':'MANUAL_REVIEW_FOR_LARGER_SHADOW_CANARY',
      'research_only':True,'live_execution':False
    }

def performance_dashboard(horizon=24):
    rows=_forward_matured(None,horizon)
    def bucket(r):
      s=fnum(r.get('champion_score'),0)
      if s>=85:return '85+'
      if s>=75:return '75-84'
      if s>=65:return '65-74'
      return '<65'
    def regime(r):return str(r.get('regime') or 'UNKNOWN')
    def source(r):return str(r.get('auto_source') or 'MANUAL')
    allvals=[r['_market_return'] if r.get('direction')=='LONG' else -r['_market_return'] for r in rows if r.get('champion_take')]
    overall=_seq_metrics(allvals); overall['profit_factor_proxy']=_pf(allvals)
    return {'horizon_h':horizon,'matured':len(rows),'overall_champion':overall,
      'by_symbol':_group_forward(rows,lambda r:r.get('symbol') or 'UNKNOWN'),
      'by_direction':_group_forward(rows,lambda r:r.get('direction') or 'UNKNOWN'),
      'by_score_bucket':_group_forward(rows,bucket),
      'by_playbook':_group_forward(rows,lambda r:r.get('playbook_primary') or 'NO_PLAYBOOK'),
      'by_regime':_group_forward(rows,regime),'by_source':_group_forward(rows,source),
      'research_only':True,'live_execution':False}

def update_forward_returns():
    rows=read_forward()
    if not rows:return {'updated':0,'rows':0}
    changed=0; now_ms=int(time.time()*1000)
    # Use Binance spot klines to mature each frozen observation at 1/4/12/24h.
    for r in rows:
      ts=int(r.get('captured_at_ms') or 0); symbol=r.get('symbol'); entry=fnum(r.get('entry'))
      if not ts or not symbol or not entry: continue
      fr=r.setdefault('forward_return_pct',{})
      for h in HORIZONS:
        key=str(h)
        if key in fr or now_ms<ts+h*3600*1000: continue
        try:
          end=ts+h*3600*1000
          path=f'/api/v3/klines?symbol={urllib.parse.quote(str(symbol))}&interval=1m&startTime={int(end)}&limit=1'
          kl=get_json_fallback([
            'https://data-api.binance.vision'+path,
            'https://api-gcp.binance.com'+path,
            'https://api1.binance.com'+path,
            'https://api2.binance.com'+path,
            'https://api3.binance.com'+path,
            'https://api4.binance.com'+path,
            'https://api.binance.com'+path,
          ],'spot')
          if isinstance(kl,list) and kl:
            px=fnum(kl[0][4])
            if px: fr[key]=round((px/entry-1)*100,6);changed+=1
        except Exception: pass
    if changed:
      tmp=FORWARD_ARCHIVE.with_suffix('.tmp')
      with tmp.open('w') as f:
        for r in rows:f.write(json.dumps(r,separators=(',',':'))+'\n')
      tmp.replace(FORWARD_ARCHIVE)
    return {'updated':changed,'rows':len(rows)}

def assess_failure_rules(symbol,current,horizon=24):
    learn=failure_learning(symbol,horizon); tags=learning_tags(current)
    indexed={x['tag']:x for x in learn.get('qualified_rules',[])}
    hits=[indexed[t] for t in tags if t in indexed]
    def family(tag):
      if 'VOLUME' in tag or 'TAKER' in tag:return 'FLOW_VOLUME'
      if 'RESISTANCE' in tag or 'SUPPORT' in tag or 'BREAKOUT' in tag or 'BREAKDOWN' in tag:return 'STRUCTURE'
      if 'FUTURES' in tag or 'FUNDING' in tag or 'CROWDING' in tag or 'SQUEEZE' in tag or 'OI_' in tag:return 'DERIVATIVES'
      if 'LIQUIDITY' in tag or 'BOOK_' in tag:return 'LIQUIDITY'
      if 'RR' in tag:return 'RISK_REWARD'
      if 'RELATIVE_STRENGTH' in tag:return 'RELATIVE_STRENGTH'
      if 'ANOMALY' in tag:return 'ANOMALY'
      return tag
    byfamily={}
    for x in hits:
      fam=family(x['tag'])
      if fam not in byfamily or x['shadow_penalty']>byfamily[fam]['shadow_penalty']: byfamily[fam]=x
    selected=sorted(byfamily.values(),key=lambda x:x['shadow_penalty'],reverse=True)[:3]
    raw=sum(x['shadow_penalty'] for x in selected)
    total=round(min(18.0,raw),2)
    return {'symbol':symbol,'current_tags':tags,'matched_rules':hits,'selected_nonoverlapping_rules':selected,'shadow_penalty':total,
            'would_reduce_score_by':total,'applied_to_final_score':False,
            'shadow_only':True,'research_only':True,'live_execution':False}

def previous(symbol):
    last=None
    for x in read_all():
      if x.get('symbol')==symbol:last=x
    return last

def previous_provider(symbol, provider):
    last=None
    for x in read_all():
      if x.get('symbol')!=symbol: continue
      p=x.get('futures_provider')
      # Older pre-provider rows were Binance USD-M.
      if p is None: p='BINANCE_USDM_PUBLIC'
      if p==provider:last=x
    return last

def orderbook_metrics(depth):
    bids=depth.get('bids',[])[:20]; asks=depth.get('asks',[])[:20]
    bid_notional=sum(fnum(p,0)*fnum(q,0) for p,q,*_ in bids)
    ask_notional=sum(fnum(p,0)*fnum(q,0) for p,q,*_ in asks)
    den=bid_notional+ask_notional
    return bid_notional,ask_notional,((bid_notional-ask_notional)/den if den else 0)

def liquidity_walls(depth, mark_price, top_n=5):
    """Observed order-book walls only. These are NOT liquidation levels."""
    px=fnum(mark_price)
    if not px: return {'bid_walls':[],'ask_walls':[]}
    def side(rows, role):
      vals=[]
      for row in rows[:100]:
        if len(row)<2: continue
        price=fnum(row[0]); qty=fnum(row[1])
        if price is None or qty is None: continue
        notional=price*qty
        vals.append({'price':price,'qty':qty,'notional':notional,'distance_pct':abs(price/px-1)*100,'role':role})
      vals.sort(key=lambda x:x['notional'], reverse=True)
      return [{**x,'price':round(x['price'],8),'qty':round(x['qty'],8),'notional':round(x['notional'],2),'distance_pct':round(x['distance_pct'],4)} for x in vals[:top_n]]
    return {'bid_walls':side(depth.get('bids',[]),'BID'),'ask_walls':side(depth.get('asks',[]),'ASK')}

def score_snapshot(funding,taker,book_imb,oi_change):
    score=0.0
    if funding is not None:
      if funding>=0.0005: score-=20
      elif funding<=-0.0005: score+=20
      elif funding>=0.0002: score-=8
      elif funding<=-0.0002: score+=8
    if taker is not None: score += max(-25,min(25,(taker-1.0)*80))
    score += max(-25,min(25,book_imb*50))
    if oi_change is not None: score += max(-15,min(15,oi_change*2))
    return round(max(-100,min(100,score)))

def _bybit_linear_capture(symbol):
    """Production public derivatives fallback for research continuity when Binance USD-M is unavailable."""
    base='https://api.bybit.com'
    q=urllib.parse.quote(symbol)
    tick=get_json(f'{base}/v5/market/tickers?category=linear&symbol={q}')
    book=get_json(f'{base}/v5/market/orderbook?category=linear&symbol={q}&limit=100')
    trades=get_json(f'{base}/v5/market/recent-trade?category=linear&symbol={q}&limit=500')
    tlist=((tick or {}).get('result') or {}).get('list') or []
    if not tlist: raise RuntimeError('Bybit ticker returned no data')
    t=tlist[0]
    bres=(book or {}).get('result') or {}
    depth={'bids':bres.get('b') or [],'asks':bres.get('a') or []}
    rlist=((trades or {}).get('result') or {}).get('list') or []
    buy_vol=sum(fnum(x.get('size'),0) for x in rlist if str(x.get('side')).lower()=='buy')
    sell_vol=sum(fnum(x.get('size'),0) for x in rlist if str(x.get('side')).lower()=='sell')
    flow_ratio=(buy_vol/sell_vol) if sell_vol else (2.0 if buy_vol else 1.0)
    bidn,askn,imb=orderbook_metrics(depth)
    mark=fnum(t.get('markPrice')); walls=liquidity_walls(depth,mark)
    oi_val=fnum(t.get('openInterest'))
    prev=previous_provider(symbol,'BYBIT_LINEAR_PUBLIC'); prev_oi=fnum(prev.get('open_interest')) if prev else None
    oi_change=((oi_val/prev_oi-1)*100) if oi_val is not None and prev_oi else None
    funding=fnum(t.get('fundingRate'))
    pc=fnum(t.get('price24hPcnt')); pc=(pc*100) if pc is not None else None
    MARKET_DATA_STATE['futures']['last_provider']='api.bybit.com'
    MARKET_DATA_STATE['futures']['last_success_at']=now_iso()
    MARKET_DATA_STATE['futures']['last_error']=None
    return {
      'schema':'ATLAS_SM_V2','captured_at':now_iso(),'captured_at_ms':int(time.time()*1000),'symbol':symbol,
      'mark_price':mark,'index_price':fnum(t.get('indexPrice')),
      'funding_rate':funding,'next_funding_time':t.get('nextFundingTime'),
      'open_interest':oi_val,'oi_change_pct':round(oi_change,5) if oi_change is not None else None,
      'taker_ratio':flow_ratio,'taker_buy_vol':buy_vol,'taker_sell_vol':sell_vol,
      'orderbook_bid_notional_top20':round(bidn,2),'orderbook_ask_notional_top20':round(askn,2),
      'orderbook_imbalance':round(imb,6),'orderbook_bid_walls':walls['bid_walls'],'orderbook_ask_walls':walls['ask_walls'],
      'price_change_24h_pct':pc,'quote_volume_24h':fnum(t.get('turnover24h')),
      'experimental_score':score_snapshot(funding,flow_ratio,imb,oi_change),'factor_label':'EXPERIMENTAL_PROVIDER_SPECIFIC_UNVALIDATED',
      'whale_exchange_flow':None,'whale_provider_status':'NOT_CONNECTED','live_execution':False,
      'futures_provider':'BYBIT_LINEAR_PUBLIC','futures_evidence_validated':False,'flow_proxy':'RECENT_500_TAKER_TRADES',
      'sources':['Bybit V5 linear public market data'],
    }

def capture(symbol):
    if symbol not in ON_DEMAND_SYMBOLS: raise ValueError('Symbol is not in the ATLAS on-demand research universe.')
    try:
      base='https://fapi.binance.com'
      premium=get_json(f'{base}/fapi/v1/premiumIndex?symbol={symbol}','futures')
      oi=get_json(f'{base}/fapi/v1/openInterest?symbol={symbol}','futures')
      takers=get_json(f'{base}/futures/data/takerlongshortRatio?symbol={symbol}&period=1h&limit=2','futures')
      depth=get_json(f'{base}/fapi/v1/depth?symbol={symbol}&limit=100','futures')
      ticker=get_json(f'{base}/fapi/v1/ticker/24hr?symbol={symbol}','futures')
      taker=takers[-1] if isinstance(takers,list) and takers else {}
      bidn,askn,imb=orderbook_metrics(depth)
      walls=liquidity_walls(depth,premium.get('markPrice'))
      oi_val=fnum(oi.get('openInterest'))
      prev=previous_provider(symbol,'BINANCE_USDM_PUBLIC'); prev_oi=fnum(prev.get('open_interest')) if prev else None
      oi_change=((oi_val/prev_oi-1)*100) if oi_val is not None and prev_oi else None
      funding=fnum(premium.get('lastFundingRate')); tr=fnum(taker.get('buySellRatio'))
      snap={
        'schema':'ATLAS_SM_V2','captured_at':now_iso(),'captured_at_ms':int(time.time()*1000),'symbol':symbol,
        'mark_price':fnum(premium.get('markPrice')),'index_price':fnum(premium.get('indexPrice')),
        'funding_rate':funding,'next_funding_time':premium.get('nextFundingTime'),
        'open_interest':oi_val,'oi_change_pct':round(oi_change,5) if oi_change is not None else None,
        'taker_ratio':tr,'taker_buy_vol':fnum(taker.get('buyVol')),'taker_sell_vol':fnum(taker.get('sellVol')),
        'orderbook_bid_notional_top20':round(bidn,2),'orderbook_ask_notional_top20':round(askn,2),
        'orderbook_imbalance':round(imb,6),'orderbook_bid_walls':walls['bid_walls'],'orderbook_ask_walls':walls['ask_walls'],
        'price_change_24h_pct':fnum(ticker.get('priceChangePercent')),'quote_volume_24h':fnum(ticker.get('quoteVolume')),
        'experimental_score':score_snapshot(funding,tr,imb,oi_change),'factor_label':'EXPERIMENTAL_UNVALIDATED',
        'whale_exchange_flow':None,'whale_provider_status':'NOT_CONNECTED','live_execution':False,
        'futures_provider':'BINANCE_USDM_PUBLIC','futures_evidence_validated':True,'flow_proxy':'BINANCE_TAKER_RATIO_1H',
        'sources':['Binance USDⓈ-M public market data'],
      }
      MARKET_DATA_STATE['futures']['last_provider']='fapi.binance.com'
      MARKET_DATA_STATE['futures']['last_success_at']=now_iso()
      MARKET_DATA_STATE['futures']['last_error']=None
    except Exception as primary_error:
      MARKET_DATA_STATE['futures']['last_error']=f'Binance USD-M unavailable: {primary_error}'
      snap=_bybit_linear_capture(symbol)
    with ARCHIVE_LOCK:
      with ARCHIVE.open('a') as f: f.write(json.dumps(snap,separators=(',',':'))+'\n')
    return snap

def active_smart_money_provider(symbol):
    rows=[x for x in read_all() if x.get('symbol')==symbol]
    if not rows:return None
    return rows[-1].get('futures_provider') or 'BINANCE_USDM_PUBLIC'

def smart_money_forward_rows(symbol=None, provider=None):
    rows=read_all()
    if symbol: rows=[x for x in rows if x.get('symbol')==symbol]
    if provider:
      rows=[x for x in rows if (x.get('futures_provider') or 'BINANCE_USDM_PUBLIC')==provider]
    bysym={s:[] for s in ON_DEMAND_SYMBOLS}
    for x in read_all():
      sx=x.get('symbol')
      xp=x.get('futures_provider') or 'BINANCE_USDM_PUBLIC'
      if sx in bysym and (not provider or xp==provider): bysym[sx].append(x)
    for s in bysym: bysym[s].sort(key=lambda x:x.get('captured_at_ms',0))
    out=[]
    for x in rows:
      base=fnum(x.get('mark_price')); t=x.get('captured_at_ms',0)
      fr={}
      if base:
        series=bysym.get(x.get('symbol'),[])
        for h in HORIZONS:
          target=t+h*3600*1000
          cand=next((y for y in series if y.get('captured_at_ms',0)>=target and y.get('captured_at_ms',0)<=target+90*60*1000),None)
          if cand and fnum(cand.get('mark_price')):
            fr[str(h)]=round((fnum(cand['mark_price'])/base-1)*100,5)
          else: fr[str(h)]=None
      y=dict(x); y['forward_return_pct']=fr; out.append(y)
    return out

def factor_stats(symbol, provider=None):
    provider=provider or active_smart_money_provider(symbol)
    rows=smart_money_forward_rows(symbol,provider)
    factors=[('funding_rate','Funding'),('oi_change_pct','OI Δ'),('taker_ratio','Taker ratio'),('orderbook_imbalance','Book imbalance'),('experimental_score','Experimental score')]
    result=[]
    for key,label in factors:
      item={'factor':label,'key':key,'horizons':{}}
      for h in HORIZONS:
        pairs=[(fnum(r.get(key)),fnum(r.get('forward_return_pct',{}).get(str(h)))) for r in rows]
        pairs=[p for p in pairs if p[0] is not None and p[1] is not None]
        corr=None
        if len(pairs)>=3:
          xs=[p[0] for p in pairs]; ys=[p[1] for p in pairs]
          mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
          num=sum((a-mx)*(b-my) for a,b in pairs)
          dx=sum((a-mx)**2 for a in xs); dy=sum((b-my)**2 for b in ys)
          corr=(num/(dx*dy)**0.5) if dx>0 and dy>0 else None
        item['horizons'][str(h)]={'n':len(pairs),'correlation':round(corr,4) if corr is not None else None}
      result.append(item)
    return result


def directional_hit_rate(key, pairs):
    hits=0; usable=0
    for x,y in pairs:
      if y==0: continue
      if key=='taker_ratio': pred=1 if x>1 else -1
      elif key=='orderbook_imbalance': pred=1 if x>0 else -1
      elif key=='oi_change_pct': pred=1 if x>0 else -1
      elif key=='funding_rate': pred=-1 if x>0 else 1
      else: pred=1 if x>0 else -1
      usable+=1
      if (y>0 and pred>0) or (y<0 and pred<0): hits+=1
    return round(hits/usable*100,2) if usable else None

def validation_summary(symbol):
    provider=active_smart_money_provider(symbol)
    rows=smart_money_forward_rows(symbol,provider)
    stats=factor_stats(symbol,provider)
    # enrich factor stats with directional hit rate per horizon
    keymap={x['key']:x for x in stats}
    for key,item in keymap.items():
      for h in HORIZONS:
        pairs=[]
        for r in rows:
          x=fnum(r.get(key)); y=fnum((r.get('forward_return_pct') or {}).get(str(h)))
          if x is not None and y is not None: pairs.append((x,y))
        item['horizons'][str(h)]['directional_hit_rate_pct']=directional_hit_rate(key,pairs)
    matured={str(h):sum(1 for r in rows if (r.get('forward_return_pct') or {}).get(str(h)) is not None) for h in HORIZONS}
    n24=matured['24']
    if n24>=200: readiness='ROBUSTNESS_TEST_READY'
    elif n24>=100: readiness='VALIDATION_READY'
    elif n24>=30: readiness='EARLY_RESEARCH'
    else: readiness='NOT_READY'
    return {'symbol':symbol,'provider':provider,'snapshots':len(rows),'matured':matured,'readiness':readiness,'stats':stats,'research_only':True,'live_execution':False}

def status():
    rows=read_all(); counts={s:0 for s in ON_DEMAND_SYMBOLS}; providers={}
    for x in rows:
      if x.get('symbol') in counts:counts[x['symbol']]+=1
      p=x.get('futures_provider') or 'BINANCE_USDM_PUBLIC'
      providers[p]=providers.get(p,0)+1
    enriched=smart_money_forward_rows()
    matured={str(h):sum(1 for x in enriched if x.get('forward_return_pct',{}).get(str(h)) is not None) for h in HORIZONS}
    return {'collector':'ATLAS_V4_2','online':True,'symbols':list(SYMBOLS),'research_universe':list(ON_DEMAND_SYMBOLS),'interval':'1h','counts':counts,
      'provider_counts':providers,'active_providers':{s:active_smart_money_provider(s) for s in SYMBOLS},
      'last_capture':rows[-1]['captured_at'] if rows else None,'archive_file':str(ARCHIVE.name),
      'matured_forward_labels':matured,'live_execution':False}

def auto_loop():
    time.sleep(3)
    while True:
      SMART_MONEY_STATE['last_started_at']=now_iso()
      cycle_ok=False
      for s in SYMBOLS:
        try:
          capture(s); SMART_MONEY_STATE['captures']+=1; cycle_ok=True
        except Exception as e:
          SMART_MONEY_STATE['errors']+=1; SMART_MONEY_STATE['last_error']=f'{s}: {e}'
          print(f'[collector] {s}: {e}')
      SMART_MONEY_STATE['cycles']+=1
      if cycle_ok:
        SMART_MONEY_STATE['last_success_at']=now_iso()
        if SMART_MONEY_STATE['captures']>=len(SYMBOLS): SMART_MONEY_STATE['last_error']=None
      time.sleep(INTERVAL_SECONDS)


def _ema(vals,n):
    if not vals:return None
    k=2/(n+1); x=vals[0]
    for v in vals[1:]:x=v*k+x*(1-k)
    return x

def _rsi(vals,n=14):
    if len(vals)<=n:return 50.0
    gains=[];losses=[]
    for i in range(len(vals)-n,len(vals)):
      d=vals[i]-vals[i-1];gains.append(max(d,0));losses.append(max(-d,0))
    ag=sum(gains)/n;al=sum(losses)/n
    if al==0:return 100.0
    rs=ag/al;return 100-(100/(1+rs))

def _atr(ks,n=14):
    if len(ks)<=n:return None
    trs=[]
    for i in range(len(ks)-n,len(ks)):
      h,l,pc=ks[i]['high'],ks[i]['low'],ks[i-1]['close']
      trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs)/len(trs) if trs else None

def _spot_klines(symbol,limit=220):
    path=f'/api/v3/klines?symbol={urllib.parse.quote(symbol)}&interval=1h&limit={int(limit)}'
    raw=get_json_fallback([
      'https://data-api.binance.vision'+path,
      'https://api-gcp.binance.com'+path,
      'https://api1.binance.com'+path,
      'https://api2.binance.com'+path,
      'https://api3.binance.com'+path,
      'https://api4.binance.com'+path,
      'https://api.binance.com'+path,
    ],'spot')
    if not isinstance(raw,list): raise RuntimeError('Invalid spot kline payload')
    return [{'time':int(x[0]),'open':fnum(x[1]),'high':fnum(x[2]),'low':fnum(x[3]),'close':fnum(x[4]),'volume':fnum(x[5])} for x in raw]

def _cloud_relative(asset,btc,n=48):
    if len(asset)<=n or len(btc)<=n:return 50.0
    ar=(asset[-1]['close']/asset[-1-n]['close']-1)*100
    br=(btc[-1]['close']/btc[-1-n]['close']-1)*100
    return max(0,min(100,50+(ar-br)*3.2))

def _cloud_sr(ks,lookback=72):
    xs=ks[-lookback:]; px=ks[-1]['close']; highs=[x['high'] for x in xs[:-1]]; lows=[x['low'] for x in xs[:-1]]
    higher=[h for h in highs if h>px]; lower=[l for l in lows if l<px]
    # No fabricated obstacle: a fresh high has no historical resistance above it in this window.
    res=min(higher) if higher else None
    sup=max(lower) if lower else None
    rd=(res/px-1)*100 if res is not None and px else None
    sd=(px/sup-1)*100 if sup is not None and px and sup else None
    return sup,res,sd,rd

def cloud_score_symbol(symbol,btc_ks):
    ks=_spot_klines(symbol)
    if len(ks)<100:return None
    closes=[x['close'] for x in ks];vols=[x['volume'] for x in ks];px=closes[-1]
    ema20=_ema(closes[-80:],20);ema50=_ema(closes[-120:],50);rsi=_rsi(closes,14);atr=_atr(ks,14)
    vol_base=sum(vols[-21:-1])/20 if len(vols)>=21 else vols[-1]
    rv=vols[-1]/vol_base if vol_base else 1
    sup,res,sd,rd=_cloud_sr(ks)
    rel=50.0 if symbol=='BTCUSDT' else _cloud_relative(ks,btc_ks)
    trend_up=bool(px>ema20>ema50); trend_down=bool(px<ema20<ema50)
    direction='LONG' if trend_up and rsi>=52 else 'SHORT' if trend_down and rsi<=48 else None
    if not direction:return None
    snap=None; futures_available=False
    try:
      snap=capture(symbol)
      futures_available=bool(snap.get('futures_evidence_validated', (snap.get('futures_provider') or 'BINANCE_USDM_PUBLIC')=='BINANCE_USDM_PUBLIC'))
    except Exception:
      snap={}
    fscore=fnum(snap.get('experimental_score'),0) if futures_available else 0
    funding=fnum(snap.get('funding_rate'),0) if futures_available else 0
    oi=fnum(snap.get('oi_change_pct'),0) if futures_available else 0
    taker=fnum(snap.get('taker_ratio'),1) if futures_available else 1
    book=fnum(snap.get('orderbook_imbalance'),0) if futures_available else 0
    base=58
    base+=min(12,max(0,(rv-1)*12))
    base+=8 if (direction=='LONG' and rel>=60) or (direction=='SHORT' and rel<=40) else -5 if (direction=='LONG' and rel<=35) or (direction=='SHORT' and rel>=65) else 0
    base+=min(10,abs(fscore)*.12) if (direction=='LONG' and fscore>0) or (direction=='SHORT' and fscore<0) else -min(10,abs(fscore)*.12)
    obstacle=rd if direction=='LONG' else sd
    if obstacle is not None:
      if obstacle<.7:base-=12
      elif obstacle<1.4:base-=6
      elif obstacle>2.5:base+=4
    score=round(max(0,min(100,base)))
    if not atr or atr<=0:return None
    if direction=='LONG' and oi>=3 and funding>=.00035 and rv<1 and rd is not None and rd<=2:pb='LEVERAGE_TRAP_LONG_RISK'
    elif direction=='SHORT' and oi>=3 and funding<=-.00035 and rv<1 and sd is not None and sd<=2:pb='LEVERAGE_TRAP_SHORT_RISK'
    elif direction=='LONG' and rv>=1.2 and trend_up:pb='BREAKOUT_CONTINUATION_LONG'
    elif direction=='SHORT' and rv>=1.2 and trend_down:pb='BREAKDOWN_CONTINUATION_SHORT'
    else:pb='TREND_PULLBACK_LONG' if direction=='LONG' else 'TREND_PULLBACK_SHORT'
    risk=atr*1.2
    reward=(res-px) if direction=='LONG' and res is not None else (px-sup) if direction=='SHORT' and sup is not None else None
    rr=(reward/risk) if reward is not None and risk>0 and reward>0 else None
    return {'symbol':symbol,'direction':direction,'entry':px,'champion_score':score,'champion_take':score>=60,
      'final_score':score,'opportunity_score':score,'execution_decision':f'{direction}_CANDIDATE' if score>=80 else f'{direction}_WATCH',
      'trade_plan_status':'PLAN_READY' if rr is not None else 'INCOMPLETE','rr_tp1':None,'rr_tp2':round(rr,3) if rr is not None else None,'anomaly_score':None,
      'portfolio_allowed':None,'futures_available':futures_available,'futures_provider':snap.get('futures_provider'),'futures_score':fscore if futures_available else None,'liquidity_score':None,'volume_quality':round(max(0,min(100,45+(rv-1)*35)),2),'relative_volume':round(rv,3),
      'funding_rate':funding,'oi_change_pct':oi,'taker_ratio':taker,'orderbook_imbalance':book,
      'relative_strength_score':round(rel,2),'regime':'TREND_UP' if trend_up else 'TREND_DOWN',
      'support_strength':60,'support_distance_pct':round(sd,3) if sd is not None else None,
      'resistance_strength':60,'resistance_distance_pct':round(rd,3) if rd is not None else None,
      'playbook_primary':pb,'playbook_score':score,'playbook_all':[pb],
      'auto_source':'CLOUD_FORWARD_ALPHA18','dedup_minutes':50}


def read_alerts(limit=None):
    out=[]
    if ALERT_ARCHIVE.exists():
      with ALERT_ARCHIVE.open() as f:
        for line in f:
          try:out.append(json.loads(line))
          except:pass
    return out[-limit:] if limit else out

def _alert_write(row):
    with ALERT_ARCHIVE.open('a') as f:f.write(json.dumps(row,separators=(',',':'))+'\n')

def evaluate_confirmed_opportunity(payload,store=False,source='MANUAL'):
    symbol=str(payload.get('symbol') or '').upper().replace('BINANCE:','')
    direction=str(payload.get('direction') or '').upper()
    score=fnum(payload.get('final_score') or payload.get('champion_score'),0)
    rr=fnum(payload.get('rr_tp2'),0)
    volume=fnum(payload.get('volume_quality'),0)
    futures=fnum(payload.get('futures_score'))
    futures_available=payload.get('futures_available', futures is not None)
    entry=fnum(payload.get('entry')); plan=str(payload.get('trade_plan_status') or '')
    execution=str(payload.get('execution_decision') or '')
    portfolio_allowed=payload.get('portfolio_allowed')
    quality=data_quality_report()
    drift=drift_report(24,30,60)

    checks=[]
    def ck(name,ok,value,threshold=None):
      checks.append({'name':name,'passed':bool(ok),'value':value,'threshold':threshold})
    ck('SUPPORTED_SYMBOL',symbol in ON_DEMAND_SYMBOLS,symbol,'supported universe')
    ck('DIRECTIONAL_SETUP',direction in ('LONG','SHORT'),direction,'LONG/SHORT')
    ck('FINAL_SCORE',score>=ALERT_MIN_SCORE,round(score,2),ALERT_MIN_SCORE)
    ck('TRADE_PLAN_READY',plan in ('PLAN_READY','READY','VALID') or bool(entry),plan or ('ENTRY_PRESENT' if entry else 'MISSING'),'valid plan')
    ck('RR_TP2',rr>=ALERT_MIN_RR,round(rr,3),ALERT_MIN_RR)
    ck('VOLUME_CONFIRMATION',volume>=ALERT_MIN_VOLUME_QUALITY,round(volume,2),ALERT_MIN_VOLUME_QUALITY)
    futures_ok=bool(futures_available and futures is not None and ((direction=='LONG' and futures>=-10) or (direction=='SHORT' and futures<=10)))
    ck('FUTURES_DATA_AVAILABLE',futures_available and futures is not None,futures_available,'required')
    ck('NO_STRONG_FUTURES_CONFLICT',futures_ok,round(futures,2) if futures is not None else None,'directional conflict absent')
    ck('EXECUTION_NOT_BLOCKED',execution!='NO_TRADE',execution or 'UNSPECIFIED','not NO_TRADE')
    ck('PORTFOLIO_RISK_ALLOWED',portfolio_allowed is True,portfolio_allowed,'explicitly allowed')
    ck('DATA_QUALITY',quality.get('status')=='HEALTHY',quality.get('status'),'HEALTHY')
    ck('DRIFT_VALIDATED',drift.get('status')=='STABLE',drift.get('status'),'STABLE')

    confirmed=all(x['passed'] for x in checks)
    nowms=int(time.time()*1000)
    cooldown=False;last=None
    if confirmed:
      for a in reversed(read_alerts(500)):
        if a.get('symbol')==symbol and a.get('direction')==direction:
          age=(nowms-int(a.get('created_at_ms',0)))/60000
          if age<ALERT_COOLDOWN_MINUTES:
            cooldown=True;last=a;break
    status='CONFIRMED' if confirmed and not cooldown else 'COOLDOWN' if confirmed else 'REJECTED'
    alert={
      'schema':'ATLAS_CONFIRMED_ALERT_V1','id':hashlib.sha256(f"{symbol}|{direction}|{nowms}|{entry}".encode()).hexdigest()[:20],
      'created_at':now_iso(),'created_at_ms':nowms,'source':source,'symbol':symbol,'direction':direction,
      'status':status,'confirmed':confirmed,'cooldown_blocked':cooldown,
      'score':round(score,2),'entry':entry,'rr_tp2':round(rr,3),'volume_quality':round(volume,2),
      'futures_score':round(futures,2) if futures is not None else None,'playbook':payload.get('playbook_primary'),
      'regime':payload.get('regime'),'checks':checks,
      'quality_status':quality.get('status'),'drift_status':drift.get('status'),
      'research_only':True,'live_execution':False
    }
    if confirmed and not cooldown and store:_alert_write(alert)
    if cooldown and last:alert['previous_alert_id']=last.get('id')
    return alert

def alert_status():
    rows=read_alerts(200)
    return {'total_alerts':len(read_alerts()),'recent':list(reversed(rows[-20:])),
            'policy':{'min_score':ALERT_MIN_SCORE,'min_rr_tp2':ALERT_MIN_RR,'min_volume_quality':ALERT_MIN_VOLUME_QUALITY,
                      'cooldown_minutes':ALERT_COOLDOWN_MINUTES},
            'research_only':True,'live_execution':False}

def cloud_forward_cycle():
    state=CLOUD_FORWARD_STATE;state['running']=True;state['last_started_at']=now_iso();state['last_error']=None;state['last_failed_stage']=None
    cycle_candidates=[]
    try:
      try:update_forward_returns()
      except Exception as e: state['errors']+=1; state['last_error']=f'forward_returns: {e}'
      state['last_failed_stage']='spot_btc'; btc=_spot_klines('BTCUSDT')
      state['last_failed_stage']='score_universe'
      for symbol in ON_DEMAND_SYMBOLS:
        try:
          x=cloud_score_symbol(symbol,btc)
          if x and x['final_score']>=CLOUD_FORWARD_MIN_SCORE:cycle_candidates.append(x)
        except Exception as e:
          state['errors']+=1; state['last_error']=f'{symbol}: {e}'
      cycle_candidates.sort(key=lambda x:x['final_score'],reverse=True)
      chosen=cycle_candidates[:CLOUD_FORWARD_MAX_PER_CYCLE]
      state['last_failed_stage']='store_candidates'
      for x in chosen:
        try:
          r=forward_observe(x)
          if isinstance(r,dict) and r.get('stored') is False:state['deduped']+=1
          else:state['stored']+=1
          try:evaluate_confirmed_opportunity(x,True,'CLOUD_FORWARD_ALPHA25_HARDENED')
          except Exception as ae:state['last_error']=f'Alert engine: {ae}'
        except Exception as e:
          state['errors']+=1;state['last_error']=str(e)
      state['last_candidates']=[{'symbol':x['symbol'],'direction':x['direction'],'score':x['final_score'],'playbook':x.get('playbook_primary')} for x in chosen]
      state['cycles']+=1; state['last_success_at']=now_iso(); state['last_failed_stage']=None
      try: stage_expansion_report(24,True)
      except Exception as e: state['last_error']=f'Stage engine: {e}'
    except Exception as e:
      state['errors']+=1;state['last_error']=str(e)
    finally:
      state['running']=False;state['last_finished_at']=now_iso()
    return dict(state)

def cloud_forward_loop():
    time.sleep(12)
    while True:
      if CLOUD_FORWARD_ENABLED:
        try:cloud_forward_cycle()
        except Exception as e:
          CLOUD_FORWARD_STATE['errors']+=1;CLOUD_FORWARD_STATE['last_error']=str(e)
      time.sleep(CLOUD_FORWARD_INTERVAL_SECONDS)

class Handler(SimpleHTTPRequestHandler):
    STATIC_EXTENSIONS={'.html','.js','.css','.png','.jpg','.jpeg','.svg','.ico','.webp'}
    SAFE_JSON_FILES={'FINAL_REAL_MARKET_TRIAL_SUMMARY.json','ATLAS_V4_FACTOR_RESEARCH.json','ATLAS_SPOT_ALPHA_LAB.json',
                     'ATLAS_SMART_MONEY_VALIDATION.json','ATLAS_SPOT_PORTFOLIO_WALKFORWARD.json','ATLAS_FINAL_OPPORTUNITY_ALPHA6.json'}
    BLOCKED_NAMES={'collector_server.py','render.yaml','requirements.txt','cloud_start.py'}
    def end_headers(self):
      self.send_header('X-Content-Type-Options','nosniff')
      self.send_header('Referrer-Policy','same-origin')
      self.send_header('X-Frame-Options','SAMEORIGIN')
      self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
      super().end_headers()
    def list_directory(self,path):
      self.send_error(403,'Directory listing disabled'); return None
    def _static_allowed(self,path):
      clean=urllib.parse.unquote(path).split('?',1)[0]
      if clean in ('','/'): return True
      rel=clean.lstrip('/')
      if rel.startswith('data/') or rel.startswith('.git/') or '..' in Path(rel).parts:return False
      if Path(rel).name in self.BLOCKED_NAMES or Path(rel).name.startswith('README_'):return False
      if Path(rel).suffix.lower()=='.json': return Path(rel).name in self.SAFE_JSON_FILES
      return Path(rel).suffix.lower() in self.STATIC_EXTENSIONS
    def _same_origin_write(self):
      origin=self.headers.get('Origin'); host=self.headers.get('Host')
      if not origin:return False
      try:return urllib.parse.urlparse(origin).netloc==host
      except:return False
    def _json(self,obj,code=200,headers=None):
      data=json.dumps(obj,indent=2).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data)))
      if headers:
        for k,v in headers.items():self.send_header(k,v)
      self.end_headers(); self.wfile.write(data)
    def do_GET(self):
      u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
      try:
        if u.path=='/health':
          return self._json({'status':'ok','service':'ATLAS_V7','uptime_seconds':round(time.time()-STARTED_AT,1),
                             'research_only':True,'live_execution':False},200)
        if u.path=='/api/system/readiness':
          cloud_age=None; smart_age=None
          try:
            if CLOUD_FORWARD_STATE.get('last_success_at'):
              cloud_age=(datetime.now(timezone.utc)-datetime.fromisoformat(CLOUD_FORWARD_STATE['last_success_at'])).total_seconds()
          except: pass
          try:
            if SMART_MONEY_STATE.get('last_success_at'):
              smart_age=(datetime.now(timezone.utc)-datetime.fromisoformat(SMART_MONEY_STATE['last_success_at'])).total_seconds()
          except: pass
          q=data_quality_report()
          cloud_ok=bool(CLOUD_FORWARD_STATE.get('cycles',0)>0 and cloud_age is not None and cloud_age<=max(7200,CLOUD_FORWARD_INTERVAL_SECONDS*2.5))
          smart_ok=bool(SMART_MONEY_STATE.get('last_success_at') and smart_age is not None and smart_age<=max(7200,INTERVAL_SECONDS*2.5))
          ready=bool(cloud_ok and q.get('status')!='DEGRADED')
          return self._json({'ready':ready,'status':'ready' if ready else 'degraded',
                             'cloud_forward_ok':cloud_ok,'smart_money_ok':smart_ok,
                             'cloud_forward':{**CLOUD_FORWARD_STATE},'smart_money':{**SMART_MONEY_STATE},
                             'market_data':MARKET_DATA_STATE,'data_quality':q,
                             'persistent_data_dir':str(DATA),'research_only':True,'live_execution':False},200)
        if u.path=='/api/smart-money/status': return self._json(status())
        if u.path=='/api/smart-money/latest':
          sym=q.get('symbol',['BTCUSDT'])[0]; rows=[x for x in read_all() if x.get('symbol')==sym]; return self._json({'snapshot':rows[-1] if rows else None})
        if u.path=='/api/smart-money/validation':
          sym=q.get('symbol',['BTCUSDT'])[0]; return self._json(validation_summary(sym))
        if u.path=='/api/smart-money/timeline':
          sym=q.get('symbol',['BTCUSDT'])[0]; limit=int(q.get('limit',['200'])[0]); provider=q.get('provider',[active_smart_money_provider(sym)])[0]
          return self._json({'symbol':sym,'provider':provider,'records':smart_money_forward_rows(sym,provider)[-limit:]})
        if u.path=='/api/smart-money/factor-stats':
          sym=q.get('symbol',['BTCUSDT'])[0]; provider=active_smart_money_provider(sym)
          return self._json({'symbol':sym,'provider':provider,'stats':factor_stats(sym,provider),'research_only':True})
        if u.path=='/api/alerts/status':
          return self._json(alert_status())
        if u.path=='/api/cloud-forward/status':
          return self._json({**CLOUD_FORWARD_STATE,'interval_seconds':CLOUD_FORWARD_INTERVAL_SECONDS,'min_score':CLOUD_FORWARD_MIN_SCORE,'max_per_cycle':CLOUD_FORWARD_MAX_PER_CYCLE,
                             'universe':list(ON_DEMAND_SYMBOLS),'market_data':MARKET_DATA_STATE,'smart_money':SMART_MONEY_STATE,
                             'research_only':True,'live_execution':False})
        if u.path=='/api/cloud-forward/run':
          return self._json({'error':'use POST /api/cloud-forward/run from the ATLAS interface'},405,headers={'Allow':'POST'})
        if u.path=='/api/data-quality':
          return self._json(data_quality_report())
        if u.path=='/api/drift':
          horizon=int(q.get('horizon',['24'])[0]); recent=int(q.get('recent',['30'])[0]); prior=int(q.get('prior',['60'])[0]); return self._json(drift_report(horizon,recent,prior))
        if u.path=='/api/adaptive/edge-table':
          horizon=int(q.get('horizon',['24'])[0]); min_n=int(q.get('min_n',['20'])[0]); return self._json(adaptive_edge_table(horizon,min_n))
        if u.path=='/api/adaptive/forward-comparison':
          horizon=int(q.get('horizon',['24'])[0]); return self._json(adaptive_forward_comparison(horizon))
        if u.path=='/api/promotion-gate':
          horizon=int(q.get('horizon',['24'])[0]); return self._json(promotion_gate(horizon))
        if u.path=='/api/canary/stages':
          horizon=int(q.get('horizon',['24'])[0]); return self._json(stage_expansion_report(horizon,False))
        if u.path=='/api/canary/stages/apply':
          return self._json({'error':'use POST /api/canary/stages/apply from the ATLAS interface'},405,headers={'Allow':'POST'})
        if u.path=='/api/canary/report':
          horizon=int(q.get('horizon',['24'])[0]); return self._json(canary_forward_report(horizon))
        if u.path=='/api/performance/dashboard':
          horizon=int(q.get('horizon',['24'])[0]); return self._json(performance_dashboard(horizon))
        if u.path=='/api/playbooks/stats':
          sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0]); return self._json(playbook_forward_stats(sym,horizon))
        if u.path=='/api/forward/stats':
          sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0]); return self._json(forward_stats(sym,horizon))
        if u.path=='/api/forward/update':
          return self._json({'error':'use POST /api/forward/update from the ATLAS interface'},405,headers={'Allow':'POST'})
        if u.path=='/api/learning/validation':
          sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0]); return self._json(validate_learning_rules(sym,horizon))
        if u.path=='/api/learning/failure-rules':
          sym=q.get('symbol',[None])[0]; horizon=int(q.get('horizon',['24'])[0]); return self._json(failure_learning(sym,horizon))
        if u.path=='/api/confluence/memory-stats':
          sym=q.get('symbol',['BTCUSDT'])[0]; return self._json(confluence_memory_stats(sym))
        if u.path=='/api/news/sources':
          return self._json({'sources':[{'id':x['id'],'name':x['name'],'tier':x['tier'],'scope':x['scope']} for x in NEWS_SOURCES],'poll_seconds':NEWS_POLL_SECONDS,'shadow_mode':True})
        if u.path=='/api/events/reactions':
          sym=q.get('symbol',[None])[0]; limit=int(q.get('limit',['100'])[0]); return self._json({'symbol':sym,'records':event_reaction_rows(sym)[-limit:],'shadow_mode':True})
        if u.path=='/api/events/latest':
          sym=q.get('symbol',[None])[0]; rows=read_event_all(); rows=[x for x in rows if (not sym or x.get('symbol')==sym)]
          return self._json({'events':rows[-100:],'shadow_mode':True,'research_only':True})
        if u.path=='/api/events/timeline':
          sym=q.get('symbol',[None])[0]; limit=int(q.get('limit',['200'])[0]); return self._json({'symbol':sym,'records':event_forward_rows(sym)[-limit:]})
        if u.path=='/api/events/surprise-stats':
          sym=q.get('symbol',[None])[0]; return self._json(economic_surprise_stats(sym))
        if u.path=='/api/events/stats':
          sym=q.get('symbol',[None])[0]; return self._json(event_stats(sym))
        if u.path=='/api/confluence/timeline':
          sym=q.get('symbol',['BTCUSDT'])[0]; limit=int(q.get('limit',['200'])[0]); return self._json({'symbol':sym,'records':confluence_forward_rows(sym)[-limit:]})
        if u.path=='/api/smart-money/export':
          rows=smart_money_forward_rows(); payload={'project':'ATLAS','stage':'V4.2_SMART_MONEY_FORWARD_RETURNS','generated_at':now_iso(),'research_only':True,'live_execution':False,'records':rows}
          return self._json(payload,headers={'Content-Disposition':'attachment; filename="ATLAS_SMART_MONEY_V4_2.json"'})
        if not self._static_allowed(u.path): return self._json({'error':'not found'},404)
        return super().do_GET()
      except Exception as e:return self._json({'error':str(e)},500)
    def do_POST(self):
      u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
      if not self._same_origin_write(): return self._json({'error':'same-origin request required'},403)
      if u.path=='/api/cloud-forward/run':
        try:return self._json(cloud_forward_cycle())
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/forward/update':
        try:return self._json(update_forward_returns())
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/canary/stages/apply':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          horizon=int(payload.get('horizon',24)); return self._json(stage_expansion_report(horizon,True))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/news/ingest':
        try:return self._json(ingest_news_once())
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/events/observe':
        try:
          n=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(n) or b'{}'); return self._json(event_observe(payload))
        except Exception as e:return self._json({'error':str(e)},400)
      if u.path=='/api/smart-money/capture':
        try:return self._json({'snapshot':capture(q.get('symbol',['BTCUSDT'])[0])})
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/adaptive/assess':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          horizon=int(payload.get('horizon',24)); return self._json(adaptive_assess(payload,horizon))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/alerts/evaluate':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          return self._json(evaluate_confirmed_opportunity(payload,bool(payload.get('store',True)),payload.get('source') or 'BROWSER_ALPHA25'))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/forward/observe':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          return self._json(forward_observe(payload))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/learning/promoted-assess':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          sym=str(payload.get('symbol') or 'BTCUSDT').upper().replace('BINANCE:',''); horizon=int(payload.get('horizon',24))
          return self._json(promoted_rule_assessment(sym,payload,horizon))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path=='/api/learning/assess':
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          sym=str(payload.get('symbol') or 'BTCUSDT').upper().replace('BINANCE:',''); horizon=int(payload.get('horizon',24))
          return self._json(assess_failure_rules(sym,payload,horizon))
        except Exception as e:return self._json({'error':str(e)},500)
      if u.path in ('/api/confluence/observe','/api/confluence/similar'):
        try:
          n=int(self.headers.get('Content-Length','0') or 0); payload=json.loads(self.rfile.read(n).decode() or '{}')
          if u.path=='/api/confluence/observe': return self._json(confluence_observe(payload))
          sym=str(payload.get('symbol') or 'BTCUSDT').upper().replace('BINANCE:','')
          return self._json(confluence_similar(sym,payload,int(payload.get('limit',20))))
        except Exception as e:return self._json({'error':str(e)},500)
      return self._json({'error':'not found'},404)

if __name__=='__main__':
    os.chdir(ROOT)
    threading.Thread(target=auto_loop,daemon=True).start()
    threading.Thread(target=news_loop,daemon=True).start()
    threading.Thread(target=cloud_forward_loop,daemon=True).start()
    print('ATLAS Smart Money Validation Collector')
    print(f'Archive: {ARCHIVE}')
    print('Auto capture: BTCUSDT + ETHUSDT every 1 hour')
    print('Forward labels: 1h / 4h / 12h / 24h')
    print(f'Cloud Forward Lab: {"ENABLED" if CLOUD_FORWARD_ENABLED else "DISABLED"} · every {CLOUD_FORWARD_INTERVAL_SECONDS//60} min · min score {CLOUD_FORWARD_MIN_SCORE}')
    print('Open the Render service URL after deploy')
    port=int(os.environ.get('PORT','8080')); print(f'Listening on port {port}'); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
