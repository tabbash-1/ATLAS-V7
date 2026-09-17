import atlas_walk_forward_costs as w

def row(ret=1.0,d='LONG',symbol='BTCUSDT',status='MATURED'):
    return {'status':status,'direction':d,'shadow_action':d,'symbol':symbol,'horizons':{'4h':{'directional_return_pct':ret/3},'8h':{'directional_return_pct':ret/2},'12h':{'directional_return_pct':ret}}}

def test_cost_is_positive_and_horizon_scaled():
    assert w.cost_pct(12)>0
    assert w.cost_pct(4)<w.cost_pct(12)
    assert w.cost_pct(12)==(2*w.FEE_BPS+2*w.SLIPPAGE_BPS+w.FUNDING_BPS_12H)/100

def test_net_return_deducts_costs_all_horizons():
    x=w.enrich(row(1.0))
    for h in w.HOURS: assert x[f'net_{h}h_return_pct'] < x[f'gross_{h}h_return_pct']

def test_research_guardrails():
    x=w.enrich(row()); assert x['research_only'] is True and x['can_override_production'] is False and x['live_execution'] is False

def test_only_matured_with_horizon_is_eligible():
    assert w.matured(row(),12) is True; assert w.matured(row(status='PARTIAL'),12) is False

def test_metrics_profit_factor_and_drawdown():
    rs=[row(1),row(-1),row(2)]; m=w.metrics(rs,12); assert m['n']==3 and m['max_drawdown_pct']>0 and m['profit_factor_net'] is not None

def test_long_short_can_be_separated():
    rs=[row(1,'LONG'),row(-1,'SHORT')]; assert w.metrics([r for r in rs if r['shadow_action']=='LONG'],12)['n']==1

def test_double_costs_never_improve_expectancy():
    rs=[row(1),row(-.2),row(.5)]; assert w.metrics(rs,12,2)['net_expectancy_pct'] <= w.metrics(rs,12,1)['net_expectancy_pct']

def test_zero_cost_net_equals_gross():
    m=w.metrics([row(1),row(-.5)],12,0); assert m['net_expectancy_pct']==m['gross_expectancy_pct']
