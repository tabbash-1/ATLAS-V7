#!/usr/bin/env python3
"""Ultra-light ATLAS Render web runtime.

Purpose: keep the public site and on-demand Production decision endpoints alive
inside a small Render instance. No background collectors, warm-up scans, cloud
forward loops, research replays, opportunity scans, reliability warm-up, or
profit-engine background jobs are started here.

Scheduled research remains on GitHub Actions. Production threshold is unchanged.
RC10.1 deep analysis is on-demand only and cannot override Production.
Research validation endpoints serve only the latest committed GitHub snapshot;
they never trigger forward/outcome reads or refresh work inside Render.
"""
import datetime as dt
import json
import os
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
RESEARCH_SNAPSHOT_STALE_HOURS = 6.0
os.environ.setdefault('ATLAS_CLOUD_FORWARD_ENABLED','0')
os.environ.setdefault('ATLAS_CLOUD_FORWARD_MIN_SCORE','68')

from render_boot_patch import apply as apply_render_boot_patch
apply_render_boot_patch()

import collector_server as atlas

if 'HYPEUSDT' not in atlas.ON_DEMAND_SYMBOLS:
    atlas.ON_DEMAND_SYMBOLS = tuple(atlas.ON_DEMAND_SYMBOLS) + ('HYPEUSDT',)
from hype_market_data import install as install_hype_market_data
install_hype_market_data(atlas)
atlas.SYMBOLS = tuple(atlas.ON_DEMAND_SYMBOLS)

_original_end_headers = atlas.Handler.end_headers
def _no_cache(self):
    self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
    self.send_header('Pragma','no-cache')
    self.send_header('Expires','0')
    _original_end_headers(self)
atlas.Handler.end_headers = _no_cache

from production_signal_scoring import (
    VERSION as PRODUCTION_SCORING_VERSION,
    candle_progress,
    install as install_scoring,
    paced_relative_volume,
)
install_scoring(atlas)
from production_continuation_scoring import install as install_continuation
install_continuation(atlas)
from production_decision_api import install as install_decision_api
install_decision_api(atlas)
from decision_engine_v7 import install as install_decision_engine
install_decision_engine(atlas)
from horizon_fit_overlay import install as install_horizon_fit
install_horizon_fit(atlas)
from execution_risk_management import install as install_execution_risk
install_execution_risk(atlas)
from ai_trade_council import install as install_ai_council
install_ai_council(atlas)

from rc10_1_deep_analysis_overlay import install as install_rc10_1_deep_analysis
install_rc10_1_deep_analysis(atlas)

from consensus_tiebreak_shadow import install as install_consensus_tiebreak_shadow
CONSENSUS_TIEBREAK_SHADOW = install_consensus_tiebreak_shadow(atlas)
from prospective_fourth_vote_shadow import install as install_fourth_vote_shadow
FOURTH_VOTE_SHADOW = install_fourth_vote_shadow(atlas)
from prospective_long_close_shadow import install as install_long_close_shadow
LONG_CLOSE_STRUCTURE_SHADOW = install_long_close_shadow(atlas)

# Final canonical product guard is intentionally installed after every component
# that can alter the live Production decision. It may demote a score-qualified
# setup to WAIT based on committed 4-12H evidence, but never changes the score,
# threshold, raw qualification, or live-execution policy.
from product_quality_gate_overlay import install as install_product_quality_gate
PRODUCT_QUALITY_GATE = install_product_quality_gate(atlas)

# Committed research reports are loaded once at boot. This adds read-only cached
# endpoints without any background worker, market fetch, outcome read, threshold
# change, or authority over the unified Production decision.
from committed_research_api import install as install_committed_research_api
COMMITTED_RESEARCH_API = install_committed_research_api(atlas, BASE)


def _snapshot_freshness(payload):
    captured = payload.get('_snapshot_captured_at') or (payload.get('runtime') or {}).get('last_finished_at')
    age_hours = None
    if captured:
        try:
            stamp = dt.datetime.fromisoformat(str(captured).replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=dt.timezone.utc)
            age_hours = max(0.0, (dt.datetime.now(dt.timezone.utc) - stamp.astimezone(dt.timezone.utc)).total_seconds() / 3600.0)
        except Exception:
            age_hours = None
    stale = age_hours is None or age_hours > RESEARCH_SNAPSHOT_STALE_HOURS
    return {
        'snapshot_captured_at': captured,
        'snapshot_age_hours': round(age_hours, 3) if age_hours is not None else None,
        'snapshot_stale_after_hours': RESEARCH_SNAPSHOT_STALE_HOURS,
        'snapshot_stale': stale,
        'current_for_research': not stale,
    }


def _load_committed_snapshot(filename, expected_version):
    path = BASE / 'status' / filename
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        if payload.get('version') != expected_version:
            raise ValueError(f'unexpected snapshot version: {payload.get("version")}')
        if not isinstance(payload.get('evaluation'), dict):
            raise ValueError('snapshot evaluation is not an object')
        payload['cached_only'] = True
        payload['background_refresh_triggered'] = False
        payload['outcome_read_triggered_by_request'] = False
        payload['research_only'] = True
        payload['live_execution'] = False
        payload['can_override_production'] = False
        payload['served_from'] = 'COMMITTED_GITHUB_ACTIONS_SNAPSHOT'
        payload['web_process_refresh_triggered'] = False
        payload.update(_snapshot_freshness(payload))
        runtime = dict(payload.get('runtime') or {})
        runtime['web_process_background_worker'] = False
        payload['runtime'] = runtime
        return payload
    except Exception as exc:
        return {
            'ok': False,
            'version': expected_version,
            'cached_only': True,
            'background_refresh_triggered': False,
            'outcome_read_triggered_by_request': False,
            'research_only': True,
            'live_execution': False,
            'can_override_production': False,
            'served_from': 'COMMITTED_GITHUB_ACTIONS_SNAPSHOT',
            'web_process_refresh_triggered': False,
            'snapshot_captured_at': None,
            'snapshot_age_hours': None,
            'snapshot_stale_after_hours': RESEARCH_SNAPSHOT_STALE_HOURS,
            'snapshot_stale': True,
            'current_for_research': False,
            'runtime': {
                'enabled': False,
                'background_only': True,
                'refreshes': 0,
                'last_error': f'{type(exc).__name__}: {exc}',
                'web_process_background_worker': False,
            },
            'evaluation': None,
        }


HISTORICAL_EVALUATION_SNAPSHOT = _load_committed_snapshot(
    'historical-evaluation-latest.json',
    'ATLAS_HISTORICAL_EVALUATION_RUNTIME_V1_BACKGROUND_ONLY',
)
PROSPECTIVE_MICROSTRUCTURE_SNAPSHOT = _load_committed_snapshot(
    'prospective-microstructure-latest.json',
    'ATLAS_PROSPECTIVE_MICROSTRUCTURE_VALIDATION_RUNTIME_V1',
)
PROSPECTIVE_MICROSTRUCTURE_SNAPSHOT['archive_read_triggered_by_request'] = False

atlas.WEB_SAFE_MODE = {
    'enabled': True,
    'background_workers': False,
    'cloud_forward_in_web_process': False,
    'production_threshold': float(atlas.CLOUD_FORWARD_MIN_SCORE),
    'research_execution_location': 'GITHUB_ACTIONS',
    'research_snapshot_serving': 'COMMITTED_SNAPSHOT_ONLY',
    'research_snapshot_stale_hours': RESEARCH_SNAPSHOT_STALE_HOURS,
    'committed_research_api': COMMITTED_RESEARCH_API,
    'rc10_1_deep_analysis': getattr(atlas, 'RC10_1_DEEP_ANALYSIS_VERSION', None),
    'consensus_tiebreak_shadow': CONSENSUS_TIEBREAK_SHADOW,
    'fourth_vote_shadow': FOURTH_VOTE_SHADOW,
    'long_close_structure_shadow': LONG_CLOSE_STRUCTURE_SHADOW,
    'product_quality_gate': PRODUCT_QUALITY_GATE,
}


def volume_diagnostic(symbol):
    symbol = str(symbol or 'BTCUSDT').upper().replace('BINANCE:', '')
    if symbol not in atlas.ON_DEMAND_SYMBOLS:
        return {'ok':False,'error':'unsupported symbol','symbol':symbol,'supported_symbols':list(atlas.ON_DEMAND_SYMBOLS),'research_only':True,'live_execution':False}
    ks = atlas._spot_klines(symbol)
    if len(ks) < 21:
        return {'ok':False,'error':'insufficient candles','symbol':symbol,'candles':len(ks),'research_only':True,'live_execution':False}
    current = ks[-1]
    current_volume = float(current.get('volume') or 0.0)
    prior = [float(x.get('volume') or 0.0) for x in ks[-21:-1]]
    prior_avg = sum(prior) / len(prior) if prior else 0.0
    raw_rv = current_volume / prior_avg if prior_avg > 0 else 1.0
    progress = candle_progress(current)
    paced_rv = paced_relative_volume(raw_rv, progress)
    return {
        'ok':True,'symbol':symbol,'current_candle_time':current.get('time') or current.get('open_time'),
        'current_volume':round(current_volume,10),'prior_20_full_volume_avg':round(prior_avg,10),
        'raw_relative_volume':round(raw_rv,6),'candle_progress':round(progress,6),'paced_relative_volume':round(paced_rv,6),
        'expected_formula':'min(4.0, raw_relative_volume / max(0.10, candle_progress))',
        'scoring_version':PRODUCTION_SCORING_VERSION,'production_threshold':float(atlas.CLOUD_FORWARD_MIN_SCORE),
        'research_only':True,'live_execution':False,
    }


class WebOnlyHandler(atlas.Handler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/web-mode':
            return self._json({'ok':True, **atlas.WEB_SAFE_MODE, 'research_only':True, 'live_execution':False})
        if parsed.path == '/api/web/volume-diagnostic':
            q = urllib.parse.parse_qs(parsed.query)
            return self._json(volume_diagnostic(q.get('symbol', ['BTCUSDT'])[0]))
        if parsed.path == '/api/research/historical-evaluation':
            return self._json(HISTORICAL_EVALUATION_SNAPSHOT)
        if parsed.path == '/api/research/prospective-microstructure-validation':
            return self._json(PROSPECTIVE_MICROSTRUCTURE_SNAPSHOT)
        if parsed.path == '/api/research/consensus-tiebreak-shadow':
            q = urllib.parse.parse_qs(parsed.query)
            symbol = q.get('symbol', ['BTCUSDT'])[0]
            try:
                result = atlas.consensus_tiebreak_shadow(symbol)
                return self._json(result, 200 if result.get('ok') else 400)
            except Exception as exc:
                return self._json({'ok':False,'error':f'{type(exc).__name__}: {exc}','source':atlas.CONSENSUS_TIEBREAK_SHADOW_VERSION,'shadow_only':True,'can_override_production':False,'research_only':True,'live_execution':False}, 500)
        return super().do_GET()

class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

if __name__ == '__main__':
    os.chdir(atlas.ROOT)
    port = int(os.environ.get('PORT','8080'))
    print('ATLAS Render WEB-ONLY safe mode', flush=True)
    print('Background workers: OFF (GitHub Actions owns scheduled research)', flush=True)
    print('Research validation API: committed snapshots only; stale snapshots are explicitly labelled', flush=True)
    print(f'Committed research API: {COMMITTED_RESEARCH_API["version"]}', flush=True)
    print('Production decision UI: ON + autoload', flush=True)
    print(f'Production scoring: {PRODUCTION_SCORING_VERSION}', flush=True)
    print(f'RC10.1 deep analysis: {atlas.RC10_1_DEEP_ANALYSIS_VERSION}', flush=True)
    print(f'Consensus tie-break shadow: {CONSENSUS_TIEBREAK_SHADOW["version"]}', flush=True)
    print(f'Fourth-vote prospective shadow: {FOURTH_VOTE_SHADOW["version"]}', flush=True)
    print(f'LONG+CLOSE prospective shadow: {LONG_CLOSE_STRUCTURE_SHADOW["version"]}', flush=True)
    print(f'4-12H product quality gate: {PRODUCT_QUALITY_GATE["version"]}', flush=True)
    print(f'Listening on {port}', flush=True)
    Server(('0.0.0.0',port), WebOnlyHandler).serve_forever(poll_interval=0.5)
