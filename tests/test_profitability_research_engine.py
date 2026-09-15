#!/usr/bin/env python3
import profitability_research_engine as p

out=p.build()
assert out['schema']=='ATLAS_PROFITABILITY_RESEARCH_V2'
assert out['product_horizon']=='4-12H'
assert out['safety']['research_only'] is True
assert out['safety']['paper_only'] is True
assert out['safety']['live_execution'] is False
assert out['safety']['can_override_production'] is False
assert out['safety']['can_change_score'] is False
assert out['safety']['can_change_threshold'] is False
v=out['validation_contract']
assert v['chronological_holdout_required'] is True
assert v['walk_forward_required'] is True
assert v['costs_required_before_promotion'] is True
assert v['multiple_testing_control_required'] is True
assert v['automatic_promotion'] is False
assert out['chronological_split']['holdout_used_for_candidate_selection'] is False
assert out['baseline']['n']>=1
assert out['stage_status']['7_production_promotion']=='BLOCKED_PENDING_PROSPECTIVE_VALIDATION'
for c in out['top_candidates']:
    assert c['discovery']['n']>=v['discovery_min_n']
    assert c['discovery']['avg_r']>0
    assert c['proof_status'] in ('DISCOVERY_ONLY','PROSPECTIVE_CHALLENGER_ELIGIBLE')
for c in out['challenger_registry']:
    assert c['stage']=='PROSPECTIVE_SHADOW'
    assert c['promotion_ready'] is False
    assert c['production_effect']=='NONE'
print('profitability research V2 safety: PASS')
