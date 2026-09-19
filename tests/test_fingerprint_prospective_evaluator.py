import json
import fingerprint_prospective_evaluator as m

def test_evaluator_uses_frozen_groups_and_costed_r(tmp_path):
 (tmp_path/"status").mkdir();ledger={"entries":[{"decision_id":"a","fingerprint_group":"MATCHED","symbol":"BTC","direction":"LONG"},{"decision_id":"b","fingerprint_group":"CONTROL","symbol":"ETH","direction":"LONG"}]};pv={"post_v2_cost_adjusted":{"rows":[{"decision_id":"a","net_r":1.2},{"decision_id":"b","net_r":-1.1}]}};(tmp_path/"status/fingerprint-prospective-ledger.json").write_text(json.dumps(ledger));(tmp_path/"status/production-validation-latest.json").write_text(json.dumps(pv));x=m.build(tmp_path);m.validate(x);assert x["groups"]["matched"]["avg_net_r"]==1.2;assert x["groups"]["control"]["avg_net_r"]==-1.1;assert x["formal_sample_ready"] is False;assert x["matched_minus_control_avg_net_r"] is None
