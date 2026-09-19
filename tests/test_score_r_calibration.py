import json
import score_r_calibration as c

def test_score_r_calibration_is_evidence_only(tmp_path):
 (tmp_path/"status").mkdir();rows=[]
 for i,s in enumerate([69,76,83,90]):
  rows.append({"decision_id":str(i),"symbol":"BTCUSDT","direction":"LONG","score":s,"product_window_checkpoints":[{"checkpoint_h":4,"matured":True,"r_multiple":0.1},{"checkpoint_h":8,"matured":True,"r_multiple":0.2},{"checkpoint_h":12,"matured":True,"r_multiple":(-1 if s>=82 else 1)}]})
 (tmp_path/"status/canonical-outcomes-latest.json").write_text(json.dumps({"signals":{"rows":rows}}));x=c.build(tmp_path);c.validate(x)
 assert x["by_horizon_score_band"]["12"]["82_PLUS"]["avg_r"]==-1.0
 assert x["safety"]["threshold_changed"] is False and x["safety"]["can_override_production"] is False
