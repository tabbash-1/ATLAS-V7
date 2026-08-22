import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import atlas_ai_server as ai

packet={'asset':{'symbol':'BINANCE:BTCUSDT'},'trade_geometry':{'current_price':100,'volatility_regime':'NORMAL'},'multi_timeframe':{'higher_timeframe_bias':'BULLISH','entry_timing_bias':'BULLISH'},'evidence':{'futures':{'score':22},'liquidity':{'score':5},'smart_money':{'experimental_score':-18},'master_conviction':{'decision':'LONG'}}}
assert ai._validation_payload(packet,{'decision':'WAIT'},'ATLAS_AI_TEST') is None

thesis={'decision':'LONG','confidence':82,'entry_zone':[99,101],'risk_reward':2.1,'market_regime':'MARKUP / BULL','decision_quality':{'quality_score':84,'trade_readiness_score':79,'gate':'PASS'}}
p=ai._validation_payload(packet,thesis,'ATLAS_AI_TEST')
assert p['symbol']=='BTCUSDT'
assert p['direction']=='LONG'
assert p['entry']==100
assert p['champion_score']==82
assert p['rr_tp2']==2.1
assert p['auto_source']=='ATLAS_AI_TEST'
tags=set(p['playbook_all'])
assert 'AI_HTF_BULLISH' in tags
assert 'AI_LTF_BULLISH' in tags
assert 'AI_VOL_NORMAL' in tags
assert 'AI_FUT_POS' in tags
assert 'AI_LIQ_NEUTRAL' in tags
assert 'AI_SM_NEG' in tags
assert 'AI_QUALITY_70_84' in tags
assert 'AI_READY_70_84' in tags
assert 'AI_RR_2_2_99' in tags
assert 'AI_MASTER_LONG' in tags

bad_packet={'asset':{'symbol':'BINANCE:ABCUSDT'},'trade_geometry':{'current_price':1}}
assert ai._validation_payload(bad_packet,{'decision':'SHORT','confidence':80,'entry_zone':[1,1.01]},'ATLAS_AI_TEST') is None
print('ATLAS AI validation + attribution tests PASS')
