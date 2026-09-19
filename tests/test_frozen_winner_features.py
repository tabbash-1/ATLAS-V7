import json
import frozen_winner_features as m

def test_only_frozen_entry_features_are_used(tmp_path):
 (tmp_path/"status").mkdir();p={"post_v2_cost_adjusted":{"rows":[{"decision_id":"a","net_r":1},{"decision_id":"b","net_r":-1}]},"rows":[{"decision_id":"a","direction":"LONG","decision_provenance":{"frozen_before_outcome":True,"score":80,"market_regime":"BREAKOUT_UP","playbook":"X","htf_v2_eligible":True,"futures_alignment":"ALIGNED","breakout_confirmed":True,"score_attribution":{}}},{"decision_id":"b","direction":"LONG","decision_provenance":None}]};(tmp_path/"status/production-validation-latest.json").write_text(json.dumps(p));x=m.build(tmp_path);m.validate(x);assert x["eligible_rows"]==1;assert x["rows"][0]["decision_id"]=="a"
