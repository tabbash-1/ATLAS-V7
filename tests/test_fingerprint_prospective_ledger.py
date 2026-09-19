import json
import fingerprint_prospective_ledger as m

def test_assignment_is_frozen_and_append_only(tmp_path):
 (tmp_path/"status").mkdir();prov={"frozen_before_outcome":True,"htf_v2_eligible":True,"breakout_confirmed":True,"playbook":"BREAKOUT_CONFIRMED_LONG","htf_alignment_class":"CONDITIONAL_ALIGNED_12H_NEUTRAL"}
 src={"rows":[{"decision_id":"a","captured_at":"2026-01-01T00:00:00Z","symbol":"BTC","direction":"LONG","decision_provenance":prov}]};(tmp_path/"status/production-validation-latest.json").write_text(json.dumps(src));x=m.build(tmp_path);m.validate(x);assert x["entries"][0]["fingerprint_group"]=="MATCHED";(tmp_path/"status/fingerprint-prospective-ledger.json").write_text(json.dumps(x));prov["htf_v2_eligible"]=False;y=m.build(tmp_path);assert y["entries"][0]["fingerprint_group"]=="MATCHED"
