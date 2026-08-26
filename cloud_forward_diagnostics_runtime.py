"""Cached diagnostics for the existing Cloud Forward cycle.

This layer does not make extra market-data calls. It wraps the exact
cloud_score_symbol invocations already performed by cloud_forward_cycle and
records why each symbol did or did not enter the chosen set. It cannot alter
Production decisions, sampling thresholds, storage, or live execution.
"""
from __future__ import annotations

import copy
import threading
import urllib.parse

VERSION='ATLAS_CLOUD_FORWARD_DIAGNOSTICS_V1_OBSERVATIONAL_ONLY'
LOCK=threading.RLock()
STATE={
    'installed':False,
    'cycles_observed':0,
    'last_cycle_started_at':None,
    'last_cycle_finished_at':None,
    'last_evaluated':[],
    'last_error':None,
    'research_only':True,
    'live_execution':False,
    'can_override_production':False,
    'extra_market_calls':False,
    'threshold_changes':False,
}
_CURRENT=[]


def install(collector):
    if STATE.get('installed'):
        return STATE

    original_score=collector.cloud_score_symbol
    original_cycle=collector.cloud_forward_cycle

    def score_wrapper(symbol,btc_ks):
        try:
            row=original_score(symbol,btc_ks)
            with LOCK:
                if row is None:
                    _CURRENT.append({'symbol':symbol,'score':None,'direction':None,'reason':'NO_DIRECTIONAL_SETUP_OR_INSUFFICIENT_DATA'})
                else:
                    score=row.get('final_score')
                    direction=row.get('direction')
                    _CURRENT.append({'symbol':symbol,'score':score,'direction':direction,'reason':'SCORED'})
            return row
        except Exception as exc:
            with LOCK:
                _CURRENT.append({'symbol':symbol,'score':None,'direction':None,'reason':'SCORE_ERROR','error':f'{type(exc).__name__}: {exc}'})
            raise

    def cycle_wrapper():
        with LOCK:
            _CURRENT.clear()
            STATE['last_cycle_started_at']=collector.now_iso()
            STATE['last_error']=None
        try:
            result=original_cycle()
            chosen={(x.get('symbol'),x.get('direction')) for x in (result.get('last_candidates') or []) if isinstance(x,dict)}
            min_score=float(getattr(collector,'CLOUD_FORWARD_MIN_SCORE',68))
            evaluated=[]
            with LOCK:
                source=copy.deepcopy(_CURRENT)
            for item in source:
                x=dict(item)
                if x.get('reason')=='SCORED':
                    try: score=float(x.get('score'))
                    except Exception: score=None
                    key=(x.get('symbol'),x.get('direction'))
                    if score is None:
                        x['reason']='INVALID_SCORE'
                    elif score < min_score:
                        x['reason']='BELOW_MIN_SCORE'
                    elif key in chosen:
                        x['reason']='CHOSEN_FOR_FORWARD_OBSERVATION'
                    else:
                        x['reason']='ABOVE_MIN_NOT_TOP_N'
                evaluated.append(x)
            with LOCK:
                STATE['last_evaluated']=evaluated
                STATE['cycles_observed']+=1
                STATE['last_cycle_finished_at']=collector.now_iso()
            return result
        except Exception as exc:
            with LOCK:
                STATE['last_error']=f'{type(exc).__name__}: {exc}'
                STATE['last_cycle_finished_at']=collector.now_iso()
            raise

    collector.cloud_score_symbol=score_wrapper
    collector.cloud_forward_cycle=cycle_wrapper
    collector.CLOUD_FORWARD_DIAGNOSTICS_STATE=STATE

    original_get=collector.Handler.do_GET
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=='/api/research/cloud-forward-diagnostics':
            state=copy.deepcopy(STATE)
            cloud=copy.deepcopy(getattr(collector,'CLOUD_FORWARD_STATE',{}) or {})
            return self._json({
                'ok':bool(state.get('installed')),
                'version':VERSION,
                'cached_only':True,
                'background_refresh_triggered':False,
                'market_call_triggered_by_request':False,
                'archive_read_triggered_by_request':False,
                'outcome_read_triggered_by_request':False,
                'research_only':True,
                'live_execution':False,
                'can_override_production':False,
                'diagnostics':state,
                'cloud_forward':{
                    'interval_seconds':getattr(collector,'CLOUD_FORWARD_INTERVAL_SECONDS',None),
                    'min_score':getattr(collector,'CLOUD_FORWARD_MIN_SCORE',None),
                    'max_per_cycle':getattr(collector,'CLOUD_FORWARD_MAX_PER_CYCLE',None),
                    **{k:cloud.get(k) for k in ('cycles','stored','deduped','errors','last_started_at','last_finished_at','last_success_at','last_error','last_failed_stage','last_candidates')},
                },
            })
        return original_get(self)
    collector.Handler.do_GET=do_GET

    STATE['installed']=True
    return STATE
