#!/usr/bin/env python3
import json, os, threading, time, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer

import collector_server as atlas

_ORIGINAL_CAPTURE = atlas.capture

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


def resilient_capture(symbol):
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

if __name__=='__main__':
    os.chdir(atlas.ROOT)
    threading.Thread(target=atlas.auto_loop,daemon=True).start()
    threading.Thread(target=atlas.news_loop,daemon=True).start()
    threading.Thread(target=atlas.cloud_forward_loop,daemon=True).start()
    port=int(os.environ.get('PORT','8080'))
    print('ATLAS V7 resilient production runtime')
    print(f'Data: {atlas.DATA}')
    print('Futures providers: Binance USD-M -> Bybit -> Kraken Futures')
    print(f'Listening on port {port}')
    ThreadingHTTPServer(('0.0.0.0',port),atlas.Handler).serve_forever()
