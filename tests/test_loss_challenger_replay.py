import loss_challenger_replay as m

def test_replay_is_evidence_only():
 x=m.build()
 m.validate(x)
 assert x["safety"]["production_impact"]=="NONE"
 assert x["safety"]["production_threshold"]==68
 assert x["interpretation"]["retrospective_only"] is True
 assert x["interpretation"]["prospective_paired_min_n"]>=30

def test_no_challenger_can_promote():
 x=m.build()
 assert all(v["formal_ready"] is False and v["promotion_allowed"] is False for v in x["challengers"].values())
