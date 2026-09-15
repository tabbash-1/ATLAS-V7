#!/usr/bin/env python3
import production_alpha_path_audit as a
x=a.build()
assert x['schema']=='ATLAS_PRODUCTION_ALPHA_PATH_AUDIT_V1'
assert x['product_horizon']=='4-12H'
assert x['scorer_file']=='production_signal_scoring.py'
assert x['formula_contract_ok'] is True
assert x['production_mutation_authorized'] is False
assert x['automatic_promotion'] is False
assert x['research_only'] is True
assert x['scoring_version']
assert 'trend_base' in x['raw_score_expression']
assert 'volume_bonus' in x['raw_score_expression']
assert 'relative_strength_adjustment' in x['raw_score_expression']
assert 'futures_adjustment' in x['raw_score_expression']
assert 'obstacle_adj' in x['raw_score_expression']
print('production alpha path audit: PASS')
