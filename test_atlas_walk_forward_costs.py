import atlas_walk_forward_costs as w

def row(ret=1.0,d='LONG',symbol='BTCUSDT',status='MATURED'):
    return {'status':status,'direction':d,'shadow_action':d,'symbol':symbol,'horizons':{'12h':{'directional_return_pct':ret}}}

def test_cost_is_positive_and_explicit():
    assert w.ROUND_TRIP_COST_PCT > 0
    assert w.ROUND_TRIP_COST_PCT == (2*w.FEE_BPS+2*w.SLIPPAGE_BPS+w.FUNDING_BPS_12H)/100

def test_net_return_deducts_costs():
    x=w.enrich(row(1.0)); assert x['net_12h_return_pct'] < x['gross_12h_return_pct']

def test_research_guardrails():
    x=w.enrich(row()); assert x['research_only'] is True and x['can_override_production'] is False and x['live_execution'] is False

def test_only_12h_matured_is_eligible():
    assert w.matured(row()) is True; assert w.matured(row(status='PARTIAL')) is False

def test_metrics_profit_factor_and_drawdown():
    rs=[w.enrich(row(1)),w.enrich(row(-1)),w.enrich(row(2))]; m=w.metrics(rs); assert m['n']==3 and m['max_drawdown_pct']>0 and m['profit_factor_net'] is not None

def test_long_short_can_be_separated():
    rs=[w.enrich(row(1,'LONG')),w.enrich(row(-1,'SHORT'))]; assert w.metrics([r for r in rs if r['shadow_action']=='LONG'])['n']==1
