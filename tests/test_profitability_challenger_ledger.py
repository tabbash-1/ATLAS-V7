#!/usr/bin/env python3
import profitability_challenger_ledger as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_PROSPECTIVE_SHADOW_V1'
assert x['stage']=='PROSPECTIVE_SHADOW'
assert x['production_mutation_authorized'] is False
assert x['research_only'] is True
assert x['promotion_policy']['automatic_promotion'] is False
assert x['promotion_policy']['requires_cost_adjusted_positive_expectancy'] is True
for c in x['challengers']:
    assert c['production_effect']=='NONE'
    if c['cost_adjusted'] is None: assert c['promotion_ready'] is False
print('prospective challenger ledger safety: PASS')
