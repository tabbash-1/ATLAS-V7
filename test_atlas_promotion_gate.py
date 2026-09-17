import atlas_promotion_gate as p

def m(n=30,e=.2,pf=1.3,dd=10): return {'n':n,'net_expectancy_pct':e,'profit_factor_net':pf,'max_drawdown_pct':dd}
def rows(n=30,val=.2,d='LONG'):
    return [{'captured_at':f'2026-09-{1+i//24:02d}T{i%24:02d}:00:00Z','shadow_action':d,'net_12h_return_pct':val} for i in range(n)]

def test_negative_expectancy_rejected(): assert p.evaluate('x',m(e=-.1),rows(),.1)['passed'] is False
def test_profit_factor_rejected(): assert p.evaluate('x',m(pf=.9),rows(),.1)['passed'] is False
def test_insufficient_sample_rejected(): assert p.evaluate('x',m(n=29),rows(29),.1)['passed'] is False
def test_drawdown_rejected(): assert p.evaluate('x',m(dd=25),rows(),.1)['passed'] is False
def test_double_cost_rejected(): assert p.evaluate('x',m(),rows(),-.01)['passed'] is False
def test_late_segment_failure_rejected():
    r=rows(15,.3)+[dict(x,net_12h_return_pct=-.2) for x in rows(15,.3)]
    assert p.evaluate('x',m(),r,.1)['passed'] is False
def test_synthetic_robust_cohort_only_reaches_manual_review_eligibility():
    e=p.evaluate('x',m(),rows(30,.3),.1); assert e['passed'] is True

def test_threshold_constant(): assert p.MIN_N==30 and p.MIN_PF==1.10 and p.MAX_DD_PCT==20.0
