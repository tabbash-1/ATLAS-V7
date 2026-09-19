import json
from pathlib import Path
import fingerprint_prospective_evaluator as evaluator
import learning_loop

def test_empty_ledger_bootstraps_learning_loop(tmp_path, monkeypatch):
    status=tmp_path/"status"; status.mkdir()
    (status/"fingerprint-prospective-ledger.json").write_text(json.dumps({
        "schema":"ATLAS_FINGERPRINT_PROSPECTIVE_LEDGER_V1","entries":[],
        "safety":{"research_only":True,"paper_only":True,"can_override_production":False,"automatic_strategy_change":False}
    }))
    (status/"production-validation-latest.json").write_text(json.dumps({"post_v2_cost_adjusted":{"rows":[]}}))
    x=evaluator.build(tmp_path); evaluator.validate(x)
    assert x["groups"]["matched"]["n"]==0
    assert x["groups"]["control"]["n"]==0
    assert x["formal_sample_ready"] is False
    assert x["edge_claim_allowed"] is False
