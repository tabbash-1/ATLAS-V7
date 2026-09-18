import production_failure_attribution as m
import paper_portfolio_10k as p


def row(r=-1.0,mfe=.2,mae=1.1,score=74,status="LOSS",tp1=False,exit_h=6,direction="SHORT",provenance=None):
    x={"id":"x","decision_id":"x","symbol":"ETHUSDT","direction":direction,
       "captured_at":"2026-09-16T00:00:00Z","captured_at_ms":1000000,
       "score":score,"threshold":68.0,
       "settlement":{"terminal":True,"r_multiple":r,"status":status,"tp1_reached":tp1,
                     "mfe_r":mfe,"mae_r":mae,"exit_at_ms":1000000+int(exit_h*3600000)},
       "product_window_checkpoints":[{"checkpoint_h":4,"r_multiple":.1},{"checkpoint_h":8,"r_multiple":-.2},{"checkpoint_h":12,"r_multiple":r}]}
    if provenance is not None: x["decision_provenance"]=provenance
    return x


def test_immediate_adverse_loss():
    d=m.diagnose(row(mfe=-.2,exit_h=.2,score=86))
    assert d["primary_attribution"]=="IMMEDIATE_ADVERSE_MOVE"
    assert "STOP_WITHIN_1H" in d["secondary_tags"]
    assert "HIGH_SCORE_ENTRY" in d["secondary_tags"]


def test_follow_through_then_reversal():
    d=m.diagnose(row(mfe=.66,exit_h=5,score=68))
    assert d["primary_attribution"]=="INSUFFICIENT_FOLLOW_THROUGH_THEN_REVERSAL"
    assert "MARGINAL_THRESHOLD_ENTRY" in d["secondary_tags"]


def test_late_reversal_tag():
    d=m.diagnose(row(mfe=.74,exit_h=11))
    assert "LATE_HORIZON_REVERSAL" in d["secondary_tags"]


def test_positive_tp1_without_tp2_is_control_not_failure():
    d=m.diagnose(row(r=.43,mfe=1.48,mae=.42,status="EXPIRED_TP1",tp1=True,exit_h=12))
    assert d["primary_attribution"]=="PARTIAL_EDGE_NO_TP2"


def test_old_rows_are_path_only_no_retroactive_guessing():
    d=m.diagnose(row())
    assert d["evidence_quality"]=="PATH_ONLY"
    assert d["decision_provenance"] is None


def test_frozen_provenance_tags_are_evidence_only():
    prov={"schema":"ATLAS_ENTRY_DECISION_PROVENANCE_V1","frozen_before_outcome":True,
          "breakout_confirmed":False,"futures_alignment":"OPPOSED","htf_alignment_class":"ALIGNED"}
    d=m.diagnose(row(provenance=prov))
    assert d["evidence_quality"]=="PATH_PLUS_FROZEN_DECISION_PROVENANCE"
    assert "ENTRY_WITHOUT_BREAKOUT_CONFIRMATION" in d["secondary_tags"]
    assert "FUTURES_OPPOSED_AT_ENTRY" in d["secondary_tags"]


def test_entry_provenance_freezer_is_compact_and_preoutcome():
    decision={"score":74,"signal_threshold":68,"candidate_direction":"SHORT",
              "production_signal_qualified":True,
              "htf_alignment_class":"ALIGNED",
              "htf_sr_decision_v2":{"regime":"4H_DIRECTIONAL_12H_NEUTRAL","eligible":True,"blockers":[]},
              "trade_plan":{"final_trade_ready_reason":"READY","entry_mode":"NOW","breakout_confirmed":True,
                            "continuation_strong":False,"scenario_reason":"ALIGNED","scenario_readiness":"READY"},
              "futures_context":{"score":45,"alignment":"ALIGNED"},
              "score_attribution":{"trend_base":68,"futures_adjustment":4.5}}
    z=p.freeze_decision_provenance(decision)
    assert z["schema"]=="ATLAS_ENTRY_DECISION_PROVENANCE_V1"
    assert z["frozen_before_outcome"] is True
    assert z["source_of_truth"]=="FINAL_TRADE_GATE"
    assert z["strategy_epoch_id"]=="HTF_SR_V2_2026-09-14"
    assert z["product_horizon"]=="4-12H" and z["production_threshold_locked"]==68
    assert z["score"]==74 and z["threshold"]==68
    assert z["futures_alignment"]=="ALIGNED"
    assert "settlement" not in z and "pnl_usd" not in z


def test_safety_contract_constants():
    assert m.THRESHOLD==68.0
    assert m.EPOCH_ID=="HTF_SR_V2_2026-09-14"


def test_path_timing_can_tag_early_favorable_reversal_without_causal_claim():
    x=row(r=-1,mfe=.7,mae=1.1,exit_h=5)
    x["settlement"]["time_to_mfe_peak_h"]=.5
    x["settlement"]["time_to_mae_peak_h"]=4.8
    d=m.diagnose(x)
    assert "EARLY_FAVORABLE_EXCURSION_THEN_REVERSAL" in d["secondary_tags"]
    assert d["time_to_mfe_peak_h"]==.5
