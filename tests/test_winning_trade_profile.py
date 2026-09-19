import json
import winning_trade_profile as m

def test_winner_profile_uses_net_r_and_is_safe(tmp_path):
 (tmp_path/"status").mkdir();p={"epoch":{"id":"X"},"post_v2_cost_adjusted":{"rows":[{"decision_id":"a","net_r":1.5,"holding_hours":4,"estimated_cost_r":.1},{"decision_id":"b","net_r":-.5,"holding_hours":2,"estimated_cost_r":.1}]},"rows":[{"decision_id":"a","symbol":"BTC","direction":"LONG","score":80,"geometry":{"rr_tp2":2},"settlement":{"mfe_r":2,"mae_r":.2,"tp1_reached":True}},{"decision_id":"b","symbol":"ETH","direction":"LONG","score":95,"geometry":{"rr_tp2":2},"settlement":{"mfe_r":.1,"mae_r":1,"tp1_reached":False}}]}
 (tmp_path/"status/production-validation-latest.json").write_text(json.dumps(p));x=m.build(tmp_path);m.validate(x);assert x["profiles"]["winners"]["n"]==1;assert x["rows"][0]["winner_after_costs"] is True;assert x["profiles"]["winners"]["avg_score"]==80;assert x["profiles"]["non_winners"]["avg_score"]==95
