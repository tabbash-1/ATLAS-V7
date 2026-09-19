import json
import fingerprint_prospective_evaluator as m

def test_evaluator_uses_only_formal_frozen_groups_and_costed_r(tmp_path):
 (tmp_path/"status").mkdir()
 ledger={"entries":[
  {"decision_id":"a","fingerprint_group":"MATCHED","evidence_class":"FORMAL_PROSPECTIVE","symbol":"BTC","direction":"LONG"},
  {"decision_id":"b","fingerprint_group":"CONTROL","evidence_class":"FORMAL_PROSPECTIVE","symbol":"ETH","direction":"LONG"},
  {"decision_id":"old","fingerprint_group":"MATCHED","evidence_class":"BACKFILL_BASELINE","symbol":"SOL","direction":"LONG"}]}
 pv={"post_v2_cost_adjusted":{"rows":[{"decision_id":"a","net_r":1.2},{"decision_id":"b","net_r":-1.1},{"decision_id":"old","net_r":9.0}]}}
 (tmp_path/"status/fingerprint-prospective-ledger.json").write_text(json.dumps(ledger));(tmp_path/"status/production-validation-latest.json").write_text(json.dumps(pv))
 x=m.build(tmp_path);m.validate(x);assert x["groups"]["matched"]["avg_net_r"]==1.2;assert x["groups"]["control"]["avg_net_r"]==-1.1
 assert len(x["settled_rows"])==2;assert x["formal_sample_ready"] is False;assert x["matched_minus_control_avg_net_r"] is None
