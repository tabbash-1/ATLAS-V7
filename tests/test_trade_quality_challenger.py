import json
import trade_quality_challenger as m

def test_challenger_is_evidence_only(tmp_path):
    (tmp_path/"status").mkdir(parents=True, exist_ok=True)
    prov={"frozen_before_outcome":True,"htf_alignment_class":"ALIGNED","futures_alignment":"OPPOSED","market_regime":"BREAKOUT_UP","playbook":"BREAKOUT_CONFIRMED_LONG","score_attribution":{"extension_guard_reason":"RSI_SANE"}}
    rows=[{"evidence_quality":"PATH_PLUS_FROZEN_DECISION_PROVENANCE","r_multiple":-1,"primary_attribution":"IMMEDIATE_ADVERSE_MOVE","decision_provenance":prov},
          {"evidence_quality":"PATH_PLUS_FROZEN_DECISION_PROVENANCE","r_multiple":2,"primary_attribution":"POSITIVE_CONTROL_TP2","decision_provenance":prov},
          {"evidence_quality":"PATH_ONLY","r_multiple":2}]
    (tmp_path/"status/production-failure-attribution-latest.json").write_text(json.dumps({"rows":rows}))
    x=m.build(tmp_path);m.validate(x)
    assert x["sample"]["frozen_rows"]==2
    assert x["baseline"]["net_r"]==1
    assert x["failure_profile"]["immediate_adverse"]==1
    assert x["sample"]["formal_model_ready"] is False
    assert x["safety"]["production_impact"]=="NONE"
    assert x["promotion_policy"]["no_threshold_tuning"] is True
