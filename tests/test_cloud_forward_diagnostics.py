#!/usr/bin/env python3
import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))

import cloud_forward_diagnostics_runtime as diag

class Handler:
    def do_GET(self): return 'orig'

class FakeCollector:
    Handler=Handler
    CLOUD_FORWARD_MIN_SCORE=68
    CLOUD_FORWARD_MAX_PER_CYCLE=3
    CLOUD_FORWARD_INTERVAL_SECONDS=3000
    CLOUD_FORWARD_STATE={'cycles':0,'stored':0,'deduped':0,'errors':0,'last_candidates':[]}
    calls=0
    @staticmethod
    def now_iso(): return '2026-08-26T06:00:00+00:00'
    @classmethod
    def cloud_score_symbol(cls,symbol,btc):
        cls.calls+=1
        if symbol=='A': return {'symbol':'A','direction':'LONG','final_score':72}
        if symbol=='B': return {'symbol':'B','direction':'SHORT','final_score':60}
        return None
    @classmethod
    def cloud_forward_cycle(cls):
        rows=[]
        for s in ('A','B','C'):
            x=cls.cloud_score_symbol(s,[])
            if x and x['final_score']>=cls.CLOUD_FORWARD_MIN_SCORE: rows.append(x)
        cls.CLOUD_FORWARD_STATE['last_candidates']=[{'symbol':x['symbol'],'direction':x['direction'],'score':x['final_score']} for x in rows[:3]]
        cls.CLOUD_FORWARD_STATE['cycles']+=1
        return dict(cls.CLOUD_FORWARD_STATE)


def main():
    diag.STATE.update({'installed':False,'cycles_observed':0,'last_evaluated':[],'last_error':None})
    diag._CURRENT.clear()
    FakeCollector.calls=0
    diag.install(FakeCollector)
    result=FakeCollector.cloud_forward_cycle()
    assert FakeCollector.calls==3, FakeCollector.calls
    assert result['last_candidates']==[{'symbol':'A','direction':'LONG','score':72}]
    rows=diag.STATE['last_evaluated']
    by={x['symbol']:x for x in rows}
    assert by['A']['reason']=='CHOSEN_FOR_FORWARD_OBSERVATION'
    assert by['B']['reason']=='BELOW_MIN_SCORE'
    assert by['C']['reason']=='NO_DIRECTIONAL_SETUP_OR_INSUFFICIENT_DATA'
    assert diag.STATE['cycles_observed']==1
    assert diag.STATE['extra_market_calls'] is False
    assert diag.STATE['threshold_changes'] is False
    print('cloud forward diagnostics tests: OK')

if __name__=='__main__': main()
