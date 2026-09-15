#!/usr/bin/env python3
import profitability_research_engine as p

out = p.build()
assert out['schema'] == 'ATLAS_PROFITABILITY_RESEARCH_V1'
assert out['product_horizon'] == '4-12H'
assert out['safety']['research_only'] is True
assert out['safety']['paper_only'] is True
assert out['safety']['live_execution'] is False
assert out['safety']['can_override_production'] is False
assert out['safety']['can_change_score'] is False
assert out['safety']['can_change_threshold'] is False
assert out['validation_contract']['chronological_holdout_required'] is True
assert out['validation_contract']['walk_forward_required'] is True
assert out['validation_contract']['costs_required_before_promotion'] is True
assert out['validation_contract']['automatic_promotion'] is False
assert out['baseline']['n'] >= 1
for c in out['top_candidates']:
    assert c['metrics']['n'] >= out['validation_contract']['discovery_min_n']
    assert c['metrics']['avg_r'] > 0
    assert c['proof_status'] == 'DISCOVERY_ONLY'
print('profitability research safety: PASS')
