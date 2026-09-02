"""Cached-only API for committed ATLAS research and paper reports.

Loaded once at web boot from repository status files. No background worker,
request-time evaluation, market-data fetch, outcome read, or Production mutation.
"""
from __future__ import annotations
import copy, datetime as dt, json, urllib.parse
from pathlib import Path

VERSION='ATLAS_COMMITTED_RESEARCH_API_V2_PAPER_PORTFOLIO'
REPORTS={
    '/api/research/offline-forward-evaluation':('offline-forward-evaluation-latest.json','ATLAS_OFFLINE_FORWARD_EVALUATION_V3_ROBUSTNESS','research'),
    '/api/research/forward-robustness-guardrails':('forward-robustness-guardrails-latest.json','ATLAS_FORWARD_ROBUSTNESS_GUARDRAILS_V1_SHADOW_ONLY','research'),
    '/api/research/prospective-direction-guardrail':('prospective-direction-guardrail-latest.json','ATLAS_PROSPECTIVE_DIRECTION_GUARDRAIL_V1_4H','research'),
    '/api/research/paper-portfolio-10k':('paper-portfolio-10k-latest.json','ATLAS_PAPER_PORTFOLIO_10K_V1_PROSPECTIVE','paper'),
}

def _parse_time(v):
    try:
        x=dt.datetime.fromisoformat(str(v).replace('Z','+00:00'))
        if x.tzinfo is None:x=x.replace(tzinfo=dt.timezone.utc)
        return x.astimezone(dt.timezone.utc)
    except Exception:return None

def _safety(raw,kind):
    if raw.get('live_execution') is not False:raise ValueError('live execution safety contract mismatch')
    if raw.get('can_override_production') is not False:raise ValueError('production override contract mismatch')
    if kind=='research' and raw.get('research_only') is not True:raise ValueError('research safety contract mismatch')
    if kind=='paper' and raw.get('paper_only') is not True:raise ValueError('paper safety contract mismatch')

def _load(base:Path,filename:str,schema:str,kind:str):
    path=base/'status'/filename
    try:
        raw=json.loads(path.read_text(encoding='utf-8'))
        if raw.get('schema')!=schema:raise ValueError(f'schema mismatch: {raw.get("schema")}')
        _safety(raw,kind)
        stamp=_parse_time(raw.get('generated_at'))
        age_h=max(0.0,(dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()/3600) if stamp else None
        raw.update({'ok':True,'cached_only':True,'served_from':'COMMITTED_GITHUB_ACTIONS_REPORT','web_process_refresh_triggered':False,'request_time_outcome_read':False,'request_time_market_fetch':False,'web_process_background_worker':False,'report_age_hours':round(age_h,3) if age_h is not None else None,'api_version':VERSION})
        return raw
    except Exception as exc:
        base_safe={'ok':False,'schema':schema,'live_execution':False,'can_override_production':False,'cached_only':True,'served_from':'COMMITTED_GITHUB_ACTIONS_REPORT','web_process_refresh_triggered':False,'request_time_outcome_read':False,'request_time_market_fetch':False,'web_process_background_worker':False,'api_version':VERSION,'error':f'{type(exc).__name__}: {exc}'}
        base_safe['paper_only' if kind=='paper' else 'research_only']=True
        return base_safe

def install(atlas,base=None):
    base=Path(base or getattr(atlas,'ROOT',Path('.')))
    payloads={path:_load(base,*spec) for path,spec in REPORTS.items()}
    original=atlas.Handler.do_GET
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path
        if path in payloads:return self._json(copy.deepcopy(payloads[path]))
        return original(self)
    atlas.Handler.do_GET=do_GET
    atlas.COMMITTED_RESEARCH_API={'version':VERSION,'cached_only':True,'background_workers':False,'endpoints':list(REPORTS),'loaded':{k:v.get('ok') for k,v in payloads.items()}}
    return atlas.COMMITTED_RESEARCH_API
