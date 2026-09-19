import json
import cost_adjusted_score_calibration as m

def test_cost_adjusted_calibration_is_evidence_only(tmp_path):
 (tmp_path/"status").mkdir();p={"rows":[{"decision_id":"a","score":85},{"decision_id":"b","score":70}],"post_v2_cost_adjusted":{"rows":[{"decision_id":"a","symbol":"BTC","direction":"LONG","net_r":-1.1,"estimated_cost_r":.1},{"decision_id":"b","symbol":"ETH","direction":"LONG","net_r":.4,"estimated_cost_r":.1}]}}
 (tmp_path/"status/production-validation-latest.json").write_text(json.dumps(p));x=m.build(tmp_path);m.validate(x)
 assert x["bands"]["82_PLUS"]["avg_net_r"]==-1.1 and x["bands"]["68_74"]["avg_net_r"]==.4
 assert x["production_threshold_changed"] is False and x["can_override_production"] is False
