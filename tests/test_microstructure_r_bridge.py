import json
import microstructure_r_bridge as m

def test_bridge_is_descriptive_and_fail_closed(tmp_path):
 (tmp_path/"status").mkdir();rows=[{"decision_id":"a","symbol":"BTC","direction":"LONG","microstructure_relation_at_entry":"ALIGNED","settlement":{"r_multiple":1}},{"decision_id":"b","symbol":"ETH","direction":"LONG","microstructure_relation_at_entry":"MIXED_OR_INSUFFICIENT","settlement":{"r_multiple":-1}}]
 (tmp_path/"status/canonical-outcomes-latest.json").write_text(json.dumps({"signals":{"rows":rows}}));x=m.build(tmp_path);m.validate(x)
 assert x["groups"]["aligned"]["avg_r"]==1.0 and x["groups"]["control"]["avg_r"]==-1.0
 assert x["can_override_production"] is False and x["interpretation"].startswith("DESCRIPTIVE")


def test_bridge_reports_missing_frozen_relation(tmp_path):
 (tmp_path/"status").mkdir();(tmp_path/"status/canonical-outcomes-latest.json").write_text(json.dumps({"signals":{"rows":[{"decision_id":"x","symbol":"BTC","direction":"LONG","settlement":{"r_multiple":1}}]}}));x=m.build(tmp_path)
 assert x["provenance_coverage"]["unknown_relation_n"]==1
 assert x["provenance_coverage"]["warning"]=="MICROSTRUCTURE_RELATION_NOT_FROZEN_IN_CANONICAL_ENTRY"
