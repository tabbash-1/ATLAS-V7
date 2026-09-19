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


def test_learning_loop_surfaces_prospective_path_replay(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(loop.failures, "build", lambda root: {"summary":{"terminal":1,"losses":1,"primary_attributions":{"X":1}}})
    monkeypatch.setattr(loop.failures, "validate", lambda x: None)
    monkeypatch.setattr(loop.replay, "build", lambda root: {"challengers":{"EARLY_THESIS_FAILURE":{"evaluated_n":1,"triggered_n":1,"observed_delta_r":0.2}}})
    monkeypatch.setattr(loop.replay, "validate", lambda x: None)
    (tmp_path/"status").mkdir()
    (tmp_path/"status/opportunity-path-replay-latest.json").write_text(json.dumps({"hypotheses":[{"id":"EARLY_THESIS_FAILURE","paired_n":4,"evaluable":4,"changed":2,"champion_net_r":-0.1,"shadow_net_r":0.1,"delta_net_r":0.2,"formal_ready":False,"promotion_allowed":False}]}))
    x=loop.build(tmp_path)
    p=x["evidence"]["candidates"]["EARLY_THESIS_FAILURE"]["prospective_evidence"]
    assert p["paired_n"]==4 and p["delta_net_r"]==0.2 and p["promotion_allowed"] is False
    assert x["evidence"]["prospective_path_replay"]["EARLY_THESIS_FAILURE"]["formal_ready"] is False
    loop.validate(x)
