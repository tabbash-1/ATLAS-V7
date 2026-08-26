from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import production_loss_autopsy as a

def row(outcome='LOSS',r=-1,tp1=False,stop=99,entry=100,rr=2,version=None):
 g={'stop_loss':stop,'rr_tp2':rr}
 if version: g['geometry_version']=version
 return {'id':'x','symbol':'BTCUSDT','direction':'LONG','score':75,'entry':entry,'terminal':True,'path_outcome':outcome,'r_multiple':r,'tp1_reached':tp1,'geometry':g}

def test_post_tp1_is_separate_failure_mode():
 r=a.build_report([row(tp1=True),row(outcome='WIN_TP2',r=2)])
 assert r['loss_cause_counts']['POST_TP1_REVERSAL']==1
 assert r['production_threshold']==68 and r['production_threshold_changed'] is False and r['production_score_adjustment']==0
 assert r['production_stop_policy_changed'] is False

def test_tight_stop_candidate_detected_without_mutating_policy():
 r=a.build_report([row(stop=99.8)])
 assert r['loss_cause_counts']['STOP_TOO_TIGHT_CANDIDATE']==1
 assert r['entry_quality_evidence']['tight_stop_loss_share_pct']==100.0
 assert r['research_recommendation']['change_production_stop_policy_now'] is False
 assert r['research_recommendation']['action']=='COLLECT_CURRENT_GEOMETRY_COHORT'

def test_pre_tp1_failure_not_blindly_called_stop_problem():
 r=a.build_report([row(stop=98,rr=2)])
 assert r['loss_cause_counts']['PRE_TP1_DIRECTION_OR_ENTRY_FAILURE']==1

def test_geometry_generations_are_separated():
 rows=[row(stop=99.8,version='LEGACY'),row(outcome='WIN_TP2',r=2,stop=98.5,version=a.CURRENT_GEOMETRY_VERSION)]
 r=a.build_report(rows)
 cohorts=r['entry_quality_evidence']['geometry_generations']
 assert cohorts['LEGACY']['tight_stop_losses']==1
 assert cohorts[a.CURRENT_GEOMETRY_VERSION]['wins']==1
 assert r['entry_quality_evidence']['generation_metadata_complete'] is True
 assert r['cohort_focus']['current']['terminal']==1
 assert r['cohort_focus']['legacy_or_other']['terminal']==1
 assert r['cohort_focus']['current_sample_ready'] is False
 assert r['research_recommendation']['action']=='COLLECT_CURRENT_GEOMETRY_COHORT'

def test_current_geometry_becomes_evaluable_only_at_30_terminal():
 rows=[row(outcome='WIN_TP2',r=2,stop=98.5,version=a.CURRENT_GEOMETRY_VERSION) for _ in range(30)]
 r=a.build_report(rows)
 assert r['schema']=='ATLAS_PRODUCTION_LOSS_AUTOPSY_V3_COHORT_AWARE'
 assert r['cohort_focus']['current']['terminal']==30
 assert r['cohort_focus']['current_sample_ready'] is True
 assert r['cohort_focus']['production_policy_evaluable'] is True
 assert r['research_recommendation']['action']=='EVALUATE_CURRENT_GEOMETRY_ONLY'
 assert r['research_recommendation']['change_production_stop_policy_now'] is False

if __name__=='__main__':
 test_post_tp1_is_separate_failure_mode(); test_tight_stop_candidate_detected_without_mutating_policy(); test_pre_tp1_failure_not_blindly_called_stop_problem(); test_geometry_generations_are_separated(); test_current_geometry_becomes_evaluable_only_at_30_terminal(); print('production loss autopsy tests: ok')
