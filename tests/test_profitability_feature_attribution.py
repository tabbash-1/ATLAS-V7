#!/usr/bin/env python3
import profitability_feature_attribution as p
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_FEATURE_ATTRIBUTION_V1'
assert x['horizon']=='4-12H'
assert x['production_mutation_authorized'] is False
assert x['automatic_promotion'] is False
assert x['research_only'] is True
assert x['chronological_discovery_n']+x['chronological_holdout_n']>0
for v in x['features'].values(): assert v['status'] in ('DESCRIPTIVE_NOT_CAUSAL','INSUFFICIENT_FEATURE_COVERAGE')
print('numeric feature attribution safety: PASS')
