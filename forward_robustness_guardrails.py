#!/usr/bin/env python3
"""Evidence-derived ATLAS guardrails, strictly research/shadow only.
Consumes the offline forward evaluation report and emits diagnostic cautions.
It cannot change Production, thresholds, visible decisions, or execution.
"""
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path

SCHEMA='ATLAS_FORWARD_ROBUSTNESS_GUARDRAILS_V1_SHADOW_ONLY'
MIN_N=20

def bad_pair(block):
    a=(block or {}).get('4') or {}; b=(block or {}).get('12') or {}
    return bool((a.get('n') or 0)>=MIN_N and (b.get('n') or 0)>=MIN_N and (a.get('mean_pct') or 0)<0 and (b.get('mean_pct') or 0)<0 and (a.get('positive_rate_pct') or 100)<45 and (b.get('positive_rate_pct') or 100)<45)

def good_4h(block):
    a=(block or {}).get('4') or {}
    return bool((a.get('n') or 0)>=30 and (a.get('mean_pct') or 0)>0.20 and (a.get('positive_rate_pct') or 0)>=55)

def fold_4h_positive(report,side):
    folds=report.get('qualified_chronological_folds') or []
    vals=[]
    for fold in folds:
        m=(((fold.get('by_direction') or {}).get(side) or {}).get('4') or {})
        if (m.get('n') or 0)>0: vals.append((m.get('mean_pct') or 0)>0)
    return len(vals)>=3 and all(vals)

def build(r):
    flags=[]
    reg=r.get('qualified_by_regime') or {}; pb=r.get('qualified_by_playbook') or {}; dirs=r.get('qualified_by_direction') or {}
    if bad_pair(reg.get('TREND_UP')):
        flags.append({'id':'CAUTION_TREND_UP_LONG_BIAS','severity':'HIGH','scope':'RESEARCH_SHADOW','evidence':{'4h':reg['TREND_UP']['4'],'12h':reg['TREND_UP']['12']},'candidate_action':'REQUIRE_ADDITIONAL_LONG_CONFIRMATION_IN_SHADOW_TEST'})
    if bad_pair(pb.get('TREND_PULLBACK_LONG')):
        flags.append({'id':'CAUTION_TREND_PULLBACK_LONG','severity':'HIGH','scope':'RESEARCH_SHADOW','evidence':{'4h':pb['TREND_PULLBACK_LONG']['4'],'12h':pb['TREND_PULLBACK_LONG']['12']},'candidate_action':'SHADOW_VETO_CANDIDATE'})
    short4=dirs.get('SHORT') or {}
    if good_4h(short4) and fold_4h_positive(r,'SHORT'):
        flags.append({'id':'SHORT_4H_EDGE_CANDIDATE','severity':'INFO','scope':'RESEARCH_SHADOW','evidence':{'4h':short4['4'],'12h':short4.get('12'),'positive_4h_all_chronological_folds':True},'candidate_action':'PROSPECTIVE_VALIDATE_4H_ONLY','not_authorized_for':'PRODUCTION_OR_12H_EXTENSION'})
    return {'schema':SCHEMA,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'research_only':True,'shadow_only':True,'live_execution':False,'can_override_production':False,'can_change_threshold':False,'source_schema':r.get('schema'),'source_generated_at':r.get('generated_at'),'minimum_sample':MIN_N,'flags':flags,'flag_count':len(flags),'promotion_policy':'NO_PRODUCTION_CHANGE_WITHOUT_NEW_PROSPECTIVE_VALIDATION'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--input',default='status/offline-forward-evaluation-latest.json'); ap.add_argument('--output',default='status/forward-robustness-guardrails-latest.json'); a=ap.parse_args()
    r=json.loads(Path(a.input).read_text()); out=build(r); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,indent=2,sort_keys=True)); print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
