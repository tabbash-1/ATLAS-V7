import profitability_trade_outcome_walk_forward as w
def test_frozen_contract():
 import profitability_trade_outcome_predictor as p
 assert p.safety()["reward_r"]==2.0 and p.safety()["risk_r"]==1.0
 assert p.safety()["production_impact"]=="NONE"
