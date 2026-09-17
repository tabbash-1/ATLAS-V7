#!/usr/bin/env python3
import profitability_entry_path_research as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_ENTRY_PATH_RESEARCH_V1'
assert x['stage']=='ENTRY_RESEARCH'
assert x['horizon']=='4-12H'
assert x['fixed_r_unit_thresholds']==[0.5,1.0,2.0]
assert x['counterfactual_entry_claim_authorized'] is False
assert x['stop_target_change_authorized'] is False
assert x['production_mutation_authorized'] is False
assert x['automatic_promotion'] is False
assert x['all_terminal']['n']>0
assert x['all_terminal']['path_n']<=x['all_terminal']['n']
for k in ('mfe_ge_1r_pct','mae_le_1r_pct','low_favorable_high_adverse_pct','large_favorable_nonpositive_outcome_pct'):
    assert k in x['all_terminal']
print('entry path research safety: PASS')
