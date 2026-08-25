import futures_provider_chain as fpc


class Atlas:
    UA = 'test'
    def now_iso(self): return '2026-08-25T00:00:00+00:00'
    def orderbook_metrics(self, depth):
        bid=sum(float(p)*float(s) for p,s in depth['bids'])
        ask=sum(float(p)*float(s) for p,s in depth['asks'])
        total=bid+ask
        return bid,ask,(bid-ask)/total if total else 0.0
    def liquidity_walls(self, depth, mark):
        return {'bid_walls': [], 'ask_walls': []}
    def previous_provider(self, symbol, provider):
        return {'open_interest': 100.0}
    def score_snapshot(self, funding, taker_ratio, imbalance, oi_change):
        return 7.0


def test_flow_ratio_uses_taker_sides():
    ratio,buy,sell=fpc._flow_ratio([{'side':'buy','sz':'6'},{'side':'sell','sz':'3'}])
    assert ratio == 2.0 and buy == 6.0 and sell == 3.0


def test_okx_normalizes_complete_contract():
    def getter(url, ua):
        if 'market/ticker' in url:
            return {'code':'0','data':[{'last':'101','open24h':'100','volCcy24h':'12345'}]}
        if 'mark-price' in url:
            return {'code':'0','data':[{'markPx':'101'}]}
        if 'funding-rate' in url:
            return {'code':'0','data':[{'fundingRate':'0.0001','nextFundingTime':'123456789','indexPx':'100.9'}]}
        if 'open-interest' in url:
            return {'code':'0','data':[{'oi':'110'}]}
        if 'market/books' in url:
            return {'code':'0','data':[{'bids':[['100','2','0','1']],'asks':[['102','1','0','1']]}]}
        if 'market/trades' in url:
            return {'code':'0','data':[{'side':'buy','sz':'4'},{'side':'sell','sz':'2'}]}
        raise AssertionError(url)
    x=fpc._okx_capture(Atlas(),'SOLUSDT',getter=getter)
    assert x['futures_provider'] == 'OKX_USDT_SWAP_PUBLIC'
    assert x['futures_evidence_validated'] is True
    assert x['taker_ratio'] == 2.0
    assert x['oi_change_pct'] == 10.0


def test_bybit_normalizes_complete_contract():
    def getter(url, ua):
        if 'tickers' in url:
            return {'retCode':0,'result':{'list':[{'markPrice':'50','indexPrice':'49.9','fundingRate':'-0.0002','openInterest':'120','nextFundingTime':'123456789','price24hPcnt':'0.02','turnover24h':'9000'}]}}
        if 'orderbook' in url:
            return {'retCode':0,'result':{'b':[['49','3']],'a':[['51','2']]}}
        if 'recent-trade' in url:
            return {'retCode':0,'result':{'list':[{'side':'Buy','size':'9'},{'side':'Sell','size':'3'}]}}
        raise AssertionError(url)
    x=fpc._bybit_capture(Atlas(),'XRPUSDT',getter=getter)
    assert x['futures_provider'] == 'BYBIT_LINEAR_PUBLIC'
    assert x['futures_evidence_validated'] is True
    assert x['taker_ratio'] == 3.0
    assert x['price_change_24h_pct'] == 2.0


def test_incomplete_contract_is_not_validated():
    assert fpc._validated(100, 0.0, 10, 0.1, None) is False


if __name__ == '__main__':
    test_flow_ratio_uses_taker_sides()
    test_okx_normalizes_complete_contract()
    test_bybit_normalizes_complete_contract()
    test_incomplete_contract_is_not_validated()
    print('futures provider chain tests: ok')
