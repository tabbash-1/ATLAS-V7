#!/usr/bin/env python3
import json, os, threading, time, urllib.parse, urllib.request, traceback
from http.server import ThreadingHTTPServer

import collector_server as atlas
import research_memory_bridge

RESEARCH_MEMORY_BRIDGE_STATE = research_memory_bridge.install(atlas)

_ORIGINAL_CAPTURE = atlas.capture
_ORIGINAL_CLOUD_SCORE = atlas.cloud_score_symbol
BOOT_ID = f"{int(time.time())}-{os.getpid()}"
RUNTIME_STARTED_AT = time.time()
WORKER_STATE = {}
_CLOUD_CONTEXT = threading.local()
CLOUD_RUNTIME_STATE = {
    'mode':'SPOT_FIRST_WITH_FRESH_SMART_MONEY_CONTEXT',
    'score_calls':0,
    'fresh_snapshot_reuses':0,
    'spot_only_fallbacks':0,
    'last_symbol':None,
    'last_score_started_at':None,
    'last_score_finished_at':None,
    'last_score_error':None,
}

KRAKEN_SYMBOLS = {
    'BTCUSDT': ('PF_XBTUSD', 'PI_XBTUSD'),
    'ETHUSDT': ('PF_ETHUSD', 'PI_ETHUSD'),
}


def _kraken_json(path):
    url='https://futures.kraken.com/derivatives/api/v3'+path
    req=urllib.request.Request(url,headers={'User-Agent':atlas.UA,'Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=18) as r:
        obj=json.loads(r.read().decode('utf-8'))
    if not isinstance(obj,dict) or str(obj.get('result','success')).lower()=='error':
        raise RuntimeError(f'Kraken Futures invalid response for {path}')
    return obj


def _kraken_capture(symbol):
    candidates=KRAKEN_SYMBOLS.get(symbol)
    if not candidates:
        raise RuntimeError('Kraken fallback supports BTCUSDT/ETHUSDT core symbols only')

    tickers=_kraken_json('/tickers').get('tickers') or []
    ticker=None; instrument=None
    for wanted in candidates:
        ticker=next((x for x in tickers if str(x.get('symbol','')).upper()==wanted),None)
        if ticker:
            instrument=wanted; break
    if not ticker or not instrument:
        raise RuntimeError(f'Kraken Futures ticker missing for {symbol}')

    book=_kraken_json('/orderbook?symbol='+urllib.parse.quote(instrument))
    ob=book.get('orderBook') or {}
    depth={'bids':ob.get('bids') or [],'asks':ob.get('asks') or []}

    history=_kraken_json('/history?symbol='+urllib.parse.quote(instrument))
    trades=history.get('history') or []
    buy_vol=sum(atlas.fnum(x.get('size'),0) for x in trades if str(x.get('side','')).lower()=='buy')
    sell_vol=sum(atlas.fnum(x.get('size'),0) for x in trades if str(x.get('side','')).lower()=='sell')
    flow_ratio=(buy_vol/sell_vol) if sell_vol else (2.0 if buy_vol else 1.0)

    bidn,askn,imb=atlas.orderbook_metrics(depth)
    mark=atlas.fnum(ticker.get('markPrice'))
    walls=atlas.liquidity_walls(depth,mark)
    oi_val=atlas.fnum(ticker.get('openInterest'))
    prev=atlas.previous_provider(symbol,'KRAKEN_FUTURES_PUBLIC')
    prev_oi=atlas.fnum(prev.get('open_interest')) if prev else None
    oi_change=((oi_val/prev_oi-1)*100) if oi_val is not None and prev_oi else None
    funding=atlas.fnum(ticker.get('fundingRate'))
    open24=atlas.fnum(ticker.get('open24h'))
    last=atlas.fnum(ticker.get('last')) or mark
    pc=((last/open24-1)*100) if last and open24 else None

    atlas.MARKET_DATA_STATE['futures']['last_provider']='futures.kraken.com'
    atlas.MARKET_DATA_STATE['futures']['last_success_at']=atlas.now_iso()
    atlas.MARKET_DATA_STATE['futures']['last_error']=None

    return {
      'schema':'ATLAS_SM_V2','captured_at':atlas.now_iso(),'captured_at_ms':int(time.time()*1000),'symbol':symbol,
      'mark_price':mark,'index_price':atlas.fnum(ticker.get('indexPrice')),
      'funding_rate':funding,'next_funding_time':None,
      'open_interest':oi_val,'oi_change_pct':round(oi_change,5) if oi_change is not None else None,
      'taker_ratio':flow_ratio,'taker_buy_vol':buy_vol,'taker_sell_vol':sell_vol,
      'orderbook_bid_notional_top20':round(bidn,2),'orderbook_ask_notional_top20':round(askn,2),
      'orderbook_imbalance':round(imb,6),'orderbook_bid_walls':walls['bid_walls'],'orderbook_ask_walls':walls['ask_walls'],
      'price_change_24h_pct':round(pc,5) if pc is not None else None,'quote_volume_24h':atlas.fnum(ticker.get('volumeQuote')),
      'experimental_score':atlas.score_snapshot(funding,flow_ratio,imb,oi_change),'factor_label':'EXPERIMENTAL_PROVIDER_SPECIFIC_UNVALIDATED',
      'whale_exchange_flow':None,'whale_provider_status':'NOT_CONNECTED','live_execution':False,
      'futures_provider':'KRAKEN_FUTURES_PUBLIC','futures_evidence_validated':False,'flow_proxy':'KRAKEN_RECENT_100_TAKER_TRADES',
      'sources':['Kraken Futures public REST market data'],
    }


def _fresh_archived_snapshot(symbol,max_age_seconds=7200):
    now_ms=int(time.time()*1000)
    for row in reversed(atlas.read_all()[-500:]):
        if row.get('symbol')!=symbol:
            continue
        ts=int(row.get('captured_at_ms') or 0)
        if ts and now_ms-ts <= max_age_seconds*1000:
            return row
        return None
    return None


def resilient_capture(symbol):
    if getattr(_CLOUD_CONTEXT,'score_universe',False):
        cached=_fresh_archived_snapshot(symbol)
        if cached is not None:
            CLOUD_RUNTIME_STATE['fresh_snapshot_reuses']+=1
            return cached
        CLOUD_RUNTIME_STATE['spot_only_fallbacks']+=1
        raise RuntimeError('No fresh archived futures context; cloud scorer continuing spot-only')

    try:
        return _ORIGINAL_CAPTURE(symbol)
    except Exception as primary:
        try:
            snap=_kraken_capture(symbol)
            with atlas.ARCHIVE_LOCK:
                with atlas.ARCHIVE.open('a') as f:
                    f.write(json.dumps(snap,separators=(',',':'))+'\n')
            return snap
        except Exception as fallback:
            atlas.MARKET_DATA_STATE['futures']['last_error']=f'Primary futures providers failed: {primary} | Kraken fallback failed: {fallback}'
            raise RuntimeError(atlas.MARKET_DATA_STATE['futures']['last_error'])


atlas.capture=resilient_capture


def fast_cloud_score_symbol(symbol,btc_ks):
    CLOUD_RUNTIME_STATE['score_calls']+=1
    CLOUD_RUNTIME_STATE['last_symbol']=symbol
    CLOUD_RUNTIME_STATE['last_score_started_at']=atlas.now_iso()
    CLOUD_RUNTIME_STATE['last_score_error']=None
    _CLOUD_CONTEXT.score_universe=True
    try:
        return _ORIGINAL_CLOUD_SCORE(symbol,btc_ks)
    except Exception as exc:
        CLOUD_RUNTIME_STATE['last_score_error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        _CLOUD_CONTEXT.score_universe=False
        CLOUD_RUNTIME_STATE['last_score_finished_at']=atlas.now_iso()


atlas.cloud_score_symbol=fast_cloud_score_symbol


def _supervise(name, target, restart_delay=5):
    state=WORKER_STATE.setdefault(name,{'starts':0,'unexpected_exits':0,'last_started_at':None,'last_exit_at':None,'last_error':None})
    while True:
        state['starts']+=1
        state['last_started_at']=atlas.now_iso()
        state['last_error']=None
        try:
            target()
            state['unexpected_exits']+=1
            state['last_exit_at']=atlas.now_iso()
            state['last_error']='worker returned unexpectedly'
            print(f'[runtime] {name} returned unexpectedly; restarting in {restart_delay}s', flush=True)
        except BaseException as exc:
            state['unexpected_exits']+=1
            state['last_exit_at']=atlas.now_iso()
            state['last_error']=f'{type(exc).__name__}: {exc}'
            print(f'[runtime] {name} crashed: {state["last_error"]}', flush=True)
            traceback.print_exc()
        time.sleep(restart_delay)


def production_readiness_snapshot():
    """One server-side source of truth for infrastructure and evidence gates."""
    blockers=[]
    storage=getattr(atlas,'STORAGE_HARDENING_STATE',{}) or {}
    bridge=RESEARCH_MEMORY_BRIDGE_STATE
    lane=CLOUD_RUNTIME_STATE.get('research_lane') or {}
    coverage=lane.get('coverage_summary') or {}

    try:
        dq=atlas.data_quality_report()
    except Exception as exc:
        dq={'quality_score':0,'error':str(exc)}
        blockers.append('DATA_QUALITY_UNAVAILABLE')

    quality=float(dq.get('quality_score') or 0)
    if quality < 90: blockers.append('DATA_QUALITY_LT_90')
    if not os.access(str(atlas.DATA), os.W_OK): blockers.append('DATA_DIR_NOT_WRITABLE')
    if not storage.get('enabled'): blockers.append('STORAGE_HARDENING_OFF')
    elif not all(storage.get(k) for k in ('forward_write_locked','confluence_write_locked','event_write_locked')):
        blockers.append('STORAGE_LOCK_INCOMPLETE')
    if not bridge.get('enabled'): blockers.append('MEMORY_BRIDGE_OFF')
    if int(bridge.get('mirror_errors') or 0) > 0: blockers.append('MEMORY_BRIDGE_ERRORS')
    integrity=bridge.get('integrity') or {}
    if not integrity.get('enabled'):
        blockers.append('INTEGRITY_GUARD_OFF')
    elif int(integrity.get('hard_integrity_errors') or 0) > 0:
        # Sparse maturity chains are safely suppressed by the bridge and are not
        # a readiness blocker. Exact-id lineage conflicts are hard faults.
        blockers.append('MEMORY_HARD_INTEGRITY_ERRORS')
    if coverage and not coverage.get('complete'): blockers.append('ASSET_COVERAGE_INCOMPLETE')
    if coverage.get('stale_assets'): blockers.append('ASSET_COVERAGE_STALE')
    if lane.get('last_failed_symbols'): blockers.append('SCORING_FAILURES_LAST_CYCLE')

    memory_by_asset={}
    memory_total=0
    matured_24=0
    for symbol in atlas.ON_DEMAND_SYMBOLS:
        try:
            stats=atlas.confluence_memory_stats(symbol)
        except Exception as exc:
            stats={'symbol':symbol,'observations':0,'matured':{},'error':str(exc)}
            blockers.append(f'MEMORY_STATS_ERROR_{symbol}')
        memory_by_asset[symbol]=stats
        memory_total += int(stats.get('observations') or 0)
        matured_24 += int((stats.get('matured') or {}).get('24') or 0)

    blockers=list(dict.fromkeys(blockers))
    infra_ready=len(blockers)==0
    evidence_status='COLLECTING'
    if matured_24 >= 30: evidence_status='EARLY_RESEARCH'
    if matured_24 >= 100 and infra_ready: evidence_status='VALIDATION_READY'

    return {
        'ok':True,
        'boot_id':BOOT_ID,
        'uptime_seconds':round(time.time()-RUNTIME_STARTED_AT,1),
        'infrastructure':{'ready':infra_ready,'blockers':blockers},
        'storage_hardening':storage,
        'memory_bridge':bridge,
        'coverage':coverage,
        'data_quality':dq,
        'pattern_memory':{
            'observations':memory_total,
            'matured_24h':matured_24,
            'by_asset':memory_by_asset,
        },
        'evidence':{
            'status':evidence_status,
            'early_research_target':30,
            'validation_target':100,
            'remaining_to_30':max(0,30-matured_24),
            'remaining_to_100':max(0,100-matured_24),
        },
        'ready_for_validation':bool(infra_ready and matured_24>=100),
        'ready_for_live_execution':False,
        'live_execution_blocker':'RESEARCH_ONLY_NOT_VALIDATED',
        'research_only':True,
        'live_execution':False,
    }


class RuntimeHandler(atlas.Handler):
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/runtime/status':
            return self._json({
                'ok':True,
                'boot_id':BOOT_ID,
                'uptime_seconds':round(time.time()-RUNTIME_STARTED_AT,1),
                'pid':os.getpid(),
                'data_dir':str(atlas.DATA),
                'workers':WORKER_STATE,
                'smart_money':atlas.SMART_MONEY_STATE,
                'cloud_forward':atlas.CLOUD_FORWARD_STATE,
                'cloud_runtime':CLOUD_RUNTIME_STATE,
                'research_memory_bridge':RESEARCH_MEMORY_BRIDGE_STATE,
                'storage_hardening':getattr(atlas,'STORAGE_HARDENING_STATE',{}),
                'production_opportunities':getattr(atlas,'PRODUCTION_OPPORTUNITY_RUNTIME_STATE',{}),
                'market_data':atlas.MARKET_DATA_STATE,
                'research_only':True,
                'live_execution':False,
            })
        if u.path=='/api/production/readiness':
            return self._json(production_readiness_snapshot())
        return super().do_GET()


class AtlasHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    request_queue_size=128


if __name__=='__main__':
    os.chdir(atlas.ROOT)
    port=int(os.environ.get('PORT','8080'))
    server=AtlasHTTPServer(('0.0.0.0',port),RuntimeHandler)

    for name,target in (
        ('smart_money',atlas.auto_loop),
        ('news',atlas.news_loop),
        ('cloud_forward',atlas.cloud_forward_loop),
    ):
        threading.Thread(target=_supervise,args=(name,target),daemon=True,name=f'atlas-{name}').start()

    print('ATLAS V7 resilient production runtime', flush=True)
    print(f'Boot ID: {BOOT_ID}', flush=True)
    print(f'Data: {atlas.DATA}', flush=True)
    print(f'Research memory bridge: enabled={RESEARCH_MEMORY_BRIDGE_STATE.get("enabled")} mirrored={RESEARCH_MEMORY_BRIDGE_STATE.get("mirrored",0)}', flush=True)
    print('Futures providers: Binance USD-M -> Bybit -> Kraken Futures', flush=True)
    print('Cloud Forward: spot-first scoring with fresh archived futures context', flush=True)
    print(f'Listening on port {port}', flush=True)
    server.serve_forever(poll_interval=0.25)
