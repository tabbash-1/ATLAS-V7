import learning_loop as m

def test_learning_loop_is_fail_closed():
 x=m.build(__import__("pathlib").Path("."))
 m.validate(x)
 assert x["safety"]["production_threshold"]==68
 assert x["safety"]["production_impact"]=="NONE"
 assert x["next_action"]=="COLLECT_PROSPECTIVE_PAIRED_EVIDENCE"

def test_human_review_is_mandatory():
 x=m.build(__import__("pathlib").Path("."))
 assert x["pipeline"][-1]=="HUMAN_REVIEW"
 assert all(v["promotion_allowed"] is False for v in x["evidence"]["candidates"].values())
