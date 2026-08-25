from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import production_loss_autopsy as a

def row(outcome='LOSS',r=-1,tp1=False,stop=99,entry=100,rr=2):
 return {'id':'x','symbol':'BTCUSDT','direction':'LONG','score':75,'entry':entry,'terminal':True,'path_outcome':outcome,'r_multiple':r,'tp1_reached':tp1,'geometry':{'stop_loss':stop,'rr_tp2':rr}}

def test_post_tp1_is_separate_failure_mode():
 r=a.build_report([row(tp1=True),row(outcome='WIN_TP2',r=2)])
 assert r['loss_cause_counts']['POST_TP1_REVERSAL']==1
 assert r['production_threshold']==68 and r['production_threshold_changed'] is False and r['production_score_adjustment']==0

def test_tight_stop_candidate_detected():
 r=a.build_report([row(stop=99.8)])
 assert r['loss_cause_counts']['STOP_TOO_TIGHT_CANDIDATE']==1

def test_pre_tp1_failure_not_blindly_called_stop_problem():
 r=a.build_report([row(stop=98,rr=2)])
 assert r['loss_cause_counts']['PRE_TP1_DIRECTION_OR_ENTRY_FAILURE']==1

if __name__=='__main__':
 test_post_tp1_is_separate_failure_mode(); test_tight_stop_candidate_detected(); test_pre_tp1_failure_not_blindly_called_stop_problem(); print('production loss autopsy tests: ok')
