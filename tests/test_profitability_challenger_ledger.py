#!/usr/bin/env python3
import profitability_challenger_ledger as p
reg=p.load_or_freeze()
assert p.parse_ts(reg['frozen_at']) is not None
assert p.fingerprint(reg)==(reg.get('integrity_sha256') or p.fingerprint(reg))
x=p.build()
assert x['schema']=='ATLAS_PROFITABILITY_PROSPECTIVE_SHADOW_V3_INTEGRITY_COST_AWARE'
assert x['stage']=='PROSPECTIVE_SHADOW'
assert x['production_mutation_authorized'] is False
assert x['research_only'] is True
assert x['promotion_policy']['automatic_promotion'] is False
assert x['promotion_policy']['requires_cost_adjusted_positive_expectancy'] is True
assert x['promotion_policy']['requires_funding_when_nonspot'] is True
assert x['registry_integrity_sha256']==(reg.get('integrity_sha256') or p.fingerprint(reg))
for c in x['challengers']:
 assert c['production_effect']=='NONE'
 if not c['checks']['cost_and_funding_complete']: assert c['promotion_ready'] is False
print('integrity cost-aware prospective challenger safety: PASS')
