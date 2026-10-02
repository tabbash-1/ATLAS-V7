#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, pathlib
from collections import Counter

ROOT=pathlib.Path(__file__).resolve().parent
OUTCOMES=ROOT/'status/canonical-outcomes-latest.json'
INTEGRITY=ROOT/'status/paper-portfolio-10k-integrity.json'
VALIDATION=ROOT/'status/production-validation-latest.json'
QUICK=ROOT/'status/quick-trade-outcomes.json'
OUT=ROOT/'status/product-readiness-latest.json'
SCHEMA='ATLAS_PRODUCT_READINESS_GATE_V2_FINAL_GATE_AUTHORITY'
SOURCE='FINAL_TRADE_GATE'
HORIZON='4-12H'
MIN_MATURED_12H=30
MIN_DIRECTIONAL_MATURED=5

def load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

def _check(name,passed,observed=None,required=None,severity='BLOCKER'):
    return {'name':name,'passed':bool(passed),'observed':observed,'required':required,'severity':severity}

def build(outcomes=None,integrity=None,attribution=None,validation=None,quick=None):
    outcomes=outcomes if outcomes is not None else load(OUTCOMES)
    integrity=integrity if integrity is not None else load(INTEGRITY)
    validation=validation if validation is not None else load(VALIDATION)
    quick=quick if quick is not None else load(QUICK)
    safety=(outcomes or {}).get('safety') or {}
    rows=list(((outcomes or {}).get('signals') or {}).get('rows') or [])
    path=(outcomes or {}).get('path_summary') or {}
    checks=[
      _check('CANONICAL_FINAL_TRADE_GATE_AUTHORITY',bool(outcomes) and outcomes.get('decision_source_of_truth')==SOURCE,None if not outcomes else outcomes.get('decision_source_of_truth'),SOURCE),
      _check('CANONICAL_4_12H_HORIZON',bool(outcomes) and outcomes.get('product_horizon')==HORIZON,None if not outcomes else outcomes.get('product_horizon'),HORIZON),
      _check('ANALYSIS_ONLY_NO_LIVE_EXECUTION',bool(outcomes) and safety.get('live_execution') is False and safety.get('can_override_production') is False,None if not outcomes else {'live_execution':safety.get('live_execution'),'can_override_production':safety.get('can_override_production')},{'live_execution':False,'can_override_production':False}),
      _check('APPEND_ONLY_CANONICAL_LEDGER',bool(integrity) and integrity.get('append_only_verified') is True,None if not integrity else integrity.get('append_only_verified'),True),
      _check('STRICT_EXECUTION_ELIGIBILITY',bool(outcomes) and outcomes.get('legacy_backfill_allowed') is False and outcomes.get('legacy_score_path_research_included') is False,None if not outcomes else {'legacy_backfill_allowed':outcomes.get('legacy_backfill_allowed'),'legacy_score_path_research_included':outcomes.get('legacy_score_path_research_included')},{'legacy_backfill_allowed':False,'legacy_score_path_research_included':False}),
    ]
    current=(validation or {}).get('current_geometry') or {}
    current_summary=current.get('summary') or {}
    current_cost=current.get('cost_adjusted') or {}
    current_version=current.get('version')
    expected_version='ATLAS_GEOMETRY_V6_MIN_1_5_ATR_INVALIDATION'
    checks.append(_check('CURRENT_GEOMETRY_V6_EVIDENCE',current_version==expected_version,current_version,expected_version,'EVIDENCE_BLOCKER'))
    dirs_summary=current_summary.get('by_direction') or {}
    n=int(current_summary.get('terminal') or 0)
    checks.append(_check('MINIMUM_MATURED_12H_SAMPLE',n>=MIN_MATURED_12H,n,MIN_MATURED_12H,'EVIDENCE_BLOCKER'))
    for d in ('LONG','SHORT'):
        ds=dirs_summary.get(d.lower()) or {}
        dn=int(ds.get('n') or 0)
        davg=ds.get('avg_r'); dnet=ds.get('net_r')
        checks.append(_check(f'MINIMUM_{d}_MATURED_SAMPLE',dn>=MIN_DIRECTIONAL_MATURED,dn,MIN_DIRECTIONAL_MATURED,'EVIDENCE_BLOCKER'))
        checks.append(_check(f'POSITIVE_{d}_FORWARD_AVERAGE_R',dn>=MIN_DIRECTIONAL_MATURED and isinstance(davg,(int,float)) and davg>0,davg,f'> 0 with >= {MIN_DIRECTIONAL_MATURED} matured','EVIDENCE_BLOCKER'))
        checks.append(_check(f'POSITIVE_{d}_FORWARD_NET_R',dn>=MIN_DIRECTIONAL_MATURED and isinstance(dnet,(int,float)) and dnet>0,dnet,f'> 0 with >= {MIN_DIRECTIONAL_MATURED} matured','EVIDENCE_BLOCKER'))
    avg_r=current_summary.get('avg_r'); net_r=current_summary.get('net_r')
    checks.append(_check('POSITIVE_FORWARD_AVERAGE_R',n>=MIN_MATURED_12H and isinstance(avg_r,(int,float)) and avg_r>0,avg_r,'> 0 after minimum sample','EVIDENCE_BLOCKER'))
    checks.append(_check('POSITIVE_FORWARD_NET_R',n>=MIN_MATURED_12H and isinstance(net_r,(int,float)) and net_r>0,net_r,'> 0 after minimum sample','EVIDENCE_BLOCKER'))
    cost=current_cost
    cost_n=int(cost.get('terminal_costed') or 0)
    cost_avg=cost.get('avg_net_r'); cost_net=cost.get('net_r'); cost_pf=cost.get('profit_factor_r')
    checks.append(_check('MINIMUM_COST_ADJUSTED_SAMPLE',cost_n>=MIN_MATURED_12H,cost_n,MIN_MATURED_12H,'EVIDENCE_BLOCKER'))
    checks.append(_check('POSITIVE_COST_ADJUSTED_AVERAGE_R',cost_n>=MIN_MATURED_12H and isinstance(cost_avg,(int,float)) and cost_avg>0,cost_avg,'> 0 after costs and minimum sample','EVIDENCE_BLOCKER'))
    checks.append(_check('POSITIVE_COST_ADJUSTED_NET_R',cost_n>=MIN_MATURED_12H and isinstance(cost_net,(int,float)) and cost_net>0,cost_net,'> 0 after costs and minimum sample','EVIDENCE_BLOCKER'))
    checks.append(_check('COST_ADJUSTED_PROFIT_FACTOR',cost_n>=MIN_MATURED_12H and isinstance(cost_pf,(int,float)) and cost_pf>1.0,cost_pf,'> 1.0 after costs and minimum sample','EVIDENCE_BLOCKER'))
    qs=(quick or {}).get('summary') or {}
    quick_n=int(qs.get('closed_or_expired') or 0)
    quick_ambiguous=sum(1 for r in ((quick or {}).get('records') or []) if r.get('status')=='AMBIGUOUS_PATH')
    checks.append(_check('QUICK_TRADE_EVIDENCE_DISCLOSED',True,{'closed_or_expired':quick_n,'ambiguous_path':quick_ambiguous},'Quick Trade is context/research only until separately validated','DISCLOSURE'))
    quick_n=int(((quick or {}).get('summary') or {}).get('total_signals') or 0)
    quick_closed=int(((quick or {}).get('summary') or {}).get('closed_or_expired') or 0)
    quick_evidence={'status':'NO_EVIDENCE' if quick_n==0 else ('IMMATURE' if quick_closed<MIN_DIRECTIONAL_MATURED else 'OBSERVED'),'signals':quick_n,'closed_or_expired':quick_closed,'can_support_readiness':bool(quick_closed>=MIN_DIRECTIONAL_MATURED)}
    technical=all(c['passed'] for c in checks if c['severity']=='BLOCKER')
    evidence=all(c['passed'] for c in checks if c['severity']=='EVIDENCE_BLOCKER')
    state='BLOCKED_TECHNICAL' if not technical else ('FORWARD_EVIDENCE_GATE_PASSED' if evidence else 'TECHNICALLY_READY_EVIDENCE_PENDING')
    return {
      'schema':SCHEMA,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
      'product_identity':'CRYPTO_TRADE_INTELLIGENCE_AND_ANALYSIS_SYSTEM','canonical_contract':SOURCE,
      'decision_source_of_truth':SOURCE,'product_horizon':HORIZON,'analysis_only':True,'live_execution':False,
      'can_override_production':False,'production_score_threshold_changed':False,'state':state,
      'technical_ready':technical,'forward_evidence_ready':evidence,
      'claim_policy':{'may_claim_technically_operational':technical,'may_claim_forward_edge_validated':evidence,'may_claim_profitable':False,'note':'Readiness is evaluated only from prospective FINAL_TRADE_GATE execution-eligible paper evidence. Profitability still requires costs and larger independent forward evidence.'},
      'preregistered_evidence_requirements':{'minimum_matured_12h_entries':MIN_MATURED_12H,'minimum_matured_per_direction':MIN_DIRECTIONAL_MATURED,'average_r':'> 0','net_r':'> 0','cost_adjusted_average_r':'> 0','cost_adjusted_net_r':'> 0','cost_adjusted_profit_factor':'> 1.0'},
      'observed':{'entries':len(rows),'current_geometry_version':current_version,'current_geometry_entries':current_summary.get('entries'),'matured_12h_terminal':n,'matured_by_direction':dirs_summary,'avg_r':avg_r,'net_r':net_r,'cost_adjusted_terminal':cost_n,'cost_adjusted_avg_r':cost_avg,'cost_adjusted_net_r':cost_net,'cost_adjusted_profit_factor':cost_pf,'append_only_verified':None if not integrity else integrity.get('append_only_verified'),'official_trade_authority':None if not outcomes else outcomes.get('official_trade_authority')},
      'checks':checks,'blockers':[c for c in checks if not c['passed']],'quick_trade_evidence':quick_evidence,
      'research_lane_excluded_from_readiness':'analyst_output','historical_post_v2_excluded_from_current_readiness':True
    }

def main():
    out=build(); OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'state':out['state'],'technical_ready':out['technical_ready'],'forward_evidence_ready':out['forward_evidence_ready'],'blockers':[b['name'] for b in out['blockers']]},sort_keys=True))
if __name__=='__main__': main()
