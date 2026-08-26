#!/usr/bin/env python3
import pathlib, sys, tempfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))

import prospective_microstructure_cohort as cohort
import prospective_microstructure_evaluator as evaluator

class FakeCollector:
    def __init__(self,root): self.DATA=pathlib.Path(root)
    def now_iso(self): return '2026-08-26T05:40:00+00:00'


def main():
    with tempfile.TemporaryDirectory() as td:
        c=FakeCollector(td)
        s1=cohort.register(c)
        assert s1['status']=='PREREGISTERED' and s1['registration_locked'] is True
        h=s1['cohort_hash']; start=s1['cohort_start_ms']
        s2=cohort.register(c)
        assert s2['cohort_hash']==h and s2['cohort_start_ms']==start

        rows=[
            # Must be rejected: pre-cohort even though it has freeze schema.
            {'id':'old','captured_at_ms':start-1,'direction':'LONG','microstructure_freeze_schema':cohort.FREEZE_SCHEMA,'microstructure_relation_at_entry':'ALIGNED','forward_return_pct':{'12':9}},
            # Must be rejected: no decision-time freeze schema.
            {'id':'nofreeze','captured_at_ms':start+1,'direction':'LONG','microstructure_relation_at_entry':'ALIGNED','forward_return_pct':{'12':9}},
            {'id':'a1','captured_at_ms':start+2,'direction':'LONG','microstructure_freeze_schema':cohort.FREEZE_SCHEMA,'microstructure_relation_at_entry':'ALIGNED','forward_return_pct':{'12':1.0,'24':2.0}},
            {'id':'c1','captured_at_ms':start+3,'direction':'SHORT','microstructure_freeze_schema':cohort.FREEZE_SCHEMA,'microstructure_relation_at_entry':'MIXED_OR_INSUFFICIENT','forward_return_pct':{'12':1.0,'24':2.0}},
        ]
        called={'n':0}
        def loader(): called['n']+=1; return rows
        report=evaluator.evaluate(s2,loader)
        assert called['n']==1 and report['outcome_loader_called'] is True
        assert report['eligible_forward_rows']==2, report
        assert report['rejected_precohort_rows']==1
        assert report['rejected_missing_freeze_schema_rows']==1
        assert report['primary']['exposed_aligned']['mean_pct']==1.0
        assert report['primary']['control_predeclared']['mean_pct']==-1.0
        assert report['status']=='COLLECTING_PREDECLARED_GROUP_SAMPLE'
        assert report['primary_edge_claim'] is False

        blocked=dict(s2); blocked['cohort_hash']='bad'
        called2={'n':0}
        def loader2(): called2['n']+=1; return rows
        b=evaluator.evaluate(blocked,loader2)
        assert b['status']=='BLOCKED' and called2['n']==0 and b['outcome_loader_called'] is False
    print('prospective microstructure validation tests: OK')

if __name__=='__main__': main()
