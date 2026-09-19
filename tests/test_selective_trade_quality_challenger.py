import json
import selective_trade_quality_challenger as m

def test_selective_quality_is_research_only(tmp_path):
 (tmp_path/"status").mkdir();a={"qualified_joint_setup_breakdown_nonoverlap_12h":{"LONG|TREND_UP|BREAKOUT_CONTINUATION_LONG":{"12":{"n":12,"mean_pct":1.4,"positive_rate_pct":66.7,"loss_le_minus_1_pct_rate":8.3}},"SHORT|TREND_DOWN|BAD":{"12":{"n":14,"mean_pct":-1.0,"positive_rate_pct":28.0,"loss_le_minus_1_pct_rate":60}}}}
 (tmp_path/"status/monthly-product-audit-latest.json").write_text(json.dumps(a));x=m.build(tmp_path);m.validate(x)
 d={z["setup_key"]:z["state"] for z in x["setups"]};assert d["LONG|TREND_UP|BREAKOUT_CONTINUATION_LONG"]=="QUALITY_CANDIDATE";assert d["SHORT|TREND_DOWN|BAD"]=="AVOIDANCE_CANDIDATE";assert x["next_stage"]=="PROSPECTIVE_CANONICAL_NET_R_VALIDATION"
