"""Background-only cached runtime for the prospective microstructure cohort."""
from __future__ import annotations

import copy
import threading
import time
import urllib.parse

import prospective_microstructure_evaluator

VERSION='ATLAS_PROSPECTIVE_MICROSTRUCTURE_VALIDATION_RUNTIME_V1'
REFRESH_SECONDS=900
STATE={
    'enabled':True,'background_only':True,'cached_only':True,'research_only':True,'live_execution':False,'can_override_production':False,
    'refreshes':0,'last_error':None,'last_started_at':None,'last_finished_at':None,'report':None,
}


def refresh(collector):
    STATE['last_started_at']=collector.now_iso()
    try:
        cohort=getattr(collector,'PROSPECTIVE_MICROSTRUCTURE_COHORT_STATE',{}) or {}
        STATE['report']=prospective_microstructure_evaluator.evaluate(cohort,collector.read_forward)
        STATE['refreshes']+=1; STATE['last_error']=None
    except Exception as exc:
        STATE['last_error']=f'{type(exc).__name__}: {exc}'
    finally:
        STATE['last_finished_at']=collector.now_iso()
    return copy.deepcopy(STATE)


def _payload():
    return {
        'ok':STATE.get('report') is not None,'version':VERSION,'cached_only':True,'background_refresh_triggered':False,
        'archive_read_triggered_by_request':False,'outcome_read_triggered_by_request':False,'research_only':True,'live_execution':False,'can_override_production':False,
        'runtime':{k:STATE.get(k) for k in ('enabled','background_only','refreshes','last_error','last_started_at','last_finished_at')},
        'evaluation':copy.deepcopy(STATE.get('report')),
    }


def install(collector):
    if getattr(collector,'PROSPECTIVE_MICROSTRUCTURE_VALIDATION_STATE',None) is STATE:
        return STATE
    collector.PROSPECTIVE_MICROSTRUCTURE_VALIDATION_STATE=STATE
    original_get=collector.Handler.do_GET
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/research/prospective-microstructure-validation':
            return self._json(_payload())
        return original_get(self)
    collector.Handler.do_GET=do_GET

    def loop():
        time.sleep(20)
        while True:
            refresh(collector)
            time.sleep(REFRESH_SECONDS)
    threading.Thread(target=loop,daemon=True,name='atlas-prospective-microstructure-validation').start()
    return STATE
