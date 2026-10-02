import profitability_trade_outcome_multi_era as m
def test_eras_nonoverlap_and_rule():
 assert all(b-a>=28*m.DAY for a,b in zip(m.ERA_TRAIN_ENDS,m.ERA_TRAIN_ENDS[1:]))
 assert len(m.ERA_TRAIN_ENDS)==4
