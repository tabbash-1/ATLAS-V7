import atlas_ai_server as ai

packet={'asset':{'symbol':'BINANCE:BTCUSDT'},'trade_geometry':{'current_price':100}}
assert ai._validation_payload(packet,{'decision':'WAIT'},'ATLAS_AI_TEST') is None

thesis={'decision':'LONG','confidence':82,'entry_zone':[99,101],'risk_reward':2.1,'market_regime':'MARKUP / BULL'}
p=ai._validation_payload(packet,thesis,'ATLAS_AI_TEST')
assert p['symbol']=='BTCUSDT'
assert p['direction']=='LONG'
assert p['entry']==100
assert p['champion_score']==82
assert p['rr_tp2']==2.1
assert p['auto_source']=='ATLAS_AI_TEST'

bad_packet={'asset':{'symbol':'BINANCE:ABCUSDT'},'trade_geometry':{'current_price':1}}
assert ai._validation_payload(bad_packet,{'decision':'SHORT','confidence':80,'entry_zone':[1,1.01]},'ATLAS_AI_TEST') is None
print('ATLAS AI validation tests PASS')
