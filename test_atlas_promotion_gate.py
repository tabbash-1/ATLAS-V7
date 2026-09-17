import atlas_promotion_gate as p

def m(n=30,ne=.2,pf=1.2,dd=10,wr=55): return {'n':n,'net_expectancy_pct':ne,'profit_factor_net':pf,'max_drawdown_pct':dd,'win_rate_net_pct':wr}
def test_pass_requires_all_evidence(): assert p.evaluate_bucket('x',m())['evidence_passed'] is True
def test_small_sample_fails(): assert p.evaluate_bucket('x',m(n=29))['evidence_passed'] is False
def test_negative_expectancy_fails(): assert p.evaluate_bucket('x',m(ne=-.01))['evidence_passed'] is False
def test_pf_fails(): assert p.evaluate_bucket('x',m(pf=.99))['evidence_passed'] is False
def test_drawdown_fails(): assert p.evaluate_bucket('x',m(dd=20.1))['evidence_passed'] is False
def test_winrate_fails(): assert p.evaluate_bucket('x',m(wr=49.9))['evidence_passed'] is False
def test_evidence_never_authorizes_production(): assert p.evaluate_bucket('x',m())['production_authorization']=='NOT_AUTHORIZED'
def test_double_cost_requirement_when_provided():
    assert p.evaluate_bucket('x',m(),{'double_cost_12h':m(ne=-.1)})['evidence_passed'] is False
