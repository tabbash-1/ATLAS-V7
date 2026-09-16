#!/usr/bin/env python3
import profitability_challenger_ledger as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_PROSPECTIVE_SHADOW_V2_COST_AWARE'
assert x['stage']=='PROSPECTIVE_SHADOW'
assert x['production_mutation_authorized'] is False
assert x['research_only'] is True
assert x['promotion_policy']['automatic_promotion'] is False
assert x['promotion_policy']['requires_cost_adjusted_positive_expectancy'] is True
assert x['promotion_policy']['requires_funding_when_nonspot'] is True
for c in x['challengers']:
 assert c['production_effect']=='NONE'
 if not c['checks']['cost_and_funding_complete']: assert c['promotion_ready'] is False
print('cost-aware prospective challenger safety: PASS')
