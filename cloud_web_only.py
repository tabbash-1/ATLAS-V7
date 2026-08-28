#!/usr/bin/env python3
"""Ultra-light ATLAS Render web runtime.

Purpose: keep the public site and on-demand Production decision endpoints alive
inside a small Render instance. No background collectors, warm-up scans, cloud
forward loops, research replays, opportunity scans, reliability warm-up, or
profit-engine background jobs are started here.

Scheduled research remains on GitHub Actions. Production threshold is unchanged.
"""
import os
import urllib.parse
from http.server import ThreadingHTTPServer

os.environ.setdefault('ATLAS_CLOUD_FORWARD_ENABLED','0')
os.environ.setdefault('ATLAS_CLOUD_FORWARD_MIN_SCORE','68')

# Always prepare the ephemeral Render UI even when this file is used directly as
# the dashboard Start Command or Docker CMD. This avoids relying on render.yaml.
from render_boot_patch import apply as apply_render_boot_patch
apply_render_boot_patch()

import collector_server as atlas

# Keep HYPE in the API universe, but do not run any boot-wide warm-up scan.
if 'HYPEUSDT' not in atlas.ON_DEMAND_SYMBOLS:
    atlas.ON_DEMAND_SYMBOLS = tuple(atlas.ON_DEMAND_SYMBOLS) + ('HYPEUSDT',)
from hype_market_data import install as install_hype_market_data
install_hype_market_data(atlas)
atlas.SYMBOLS = tuple(atlas.ON_DEMAND_SYMBOLS)

# No-cache for decision/status responses after deploys.
_original_end_headers = atlas.Handler.end_headers
def _no_cache(self):
    self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
    self.send_header('Pragma','no-cache')
    self.send_header('Expires','0')
    _original_end_headers(self)
atlas.Handler.end_headers = _no_cache

# Minimal Production stack only. Intentionally omitted:
# production_reliability (concurrent universe warm-up), production_opportunity_runtime
# (background scans), profit_engine_runtime, outcome/calibration workers, cloud/news loops.
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

# Research-only prospective shadows. They are deliberately installed after the
# Production decision function and only expose separate endpoints. Neither can
# override Production, lower threshold 68, or execute orders.
from consensus_tiebreak_shadow import install as install_consensus_tiebreak_shadow
CONSENSUS_TIEBREAK_SHADOW = install_consensus_tiebreak_shadow(atlas)
from prospective_fourth_vote_shadow import install as install_fourth_vote_shadow
FOURTH_VOTE_SHADOW = install_fourth_vote_shadow(atlas)

# Expose explicit web-safe mode for UI/ops diagnostics.
atlas.WEB_SAFE_MODE = {
    'enabled': True,
    'background_workers': False,
    'cloud_forward_in_web_process': False,
    'production_threshold': float(atlas.CLOUD_FORWARD_MIN_SCORE),
    'research_execution_location': 'GITHUB_ACTIONS',
    'consensus_tiebreak_shadow': CONSENSUS_TIEBREAK_SHADOW,
    'fourth_vote_shadow': FOURTH_VOTE_SHADOW,
}


def volume_diagnostic(symbol):
    symbol = str(symbol or 'BTCUSDT').upper().replace('BINANCE:', '')
    if symbol not in atlas.ON_DEMAND_SYMBOLS:
        return {
            'ok': False,
            'error': 'unsupported symbol',
            'symbol': symbol,
            'supported_symbols': list(atlas.ON_DEMAND_SYMBOLS),
            'research_only': True,
            'live_execution': False,
        }
    ks = atlas._spot_klines(symbol)
    if len(ks) < 21:
        return {
            'ok': False,
            'error': 'insufficient candles',
            'symbol': symbol,
            'candles': len(ks),
            'research_only': True,
            'live_execution': False,
        }
    current = ks[-1]
    current_volume = float(current.get('volume') or 0.0)
    prior = [float(x.get('volume') or 0.0) for x in ks[-21:-1]]
    prior_avg = sum(prior) / len(prior) if prior else 0.0
    raw_rv = current_volume / prior_avg if prior_avg > 0 else 1.0
    progress = candle_progress(current)
    paced_rv = paced_relative_volume(raw_rv, progress)
    return {
        'ok': True,
        'symbol': symbol,
        'current_candle_time': current.get('time') or current.get('open_time'),
        'current_volume': round(current_volume, 10),
        'prior_20_full_volume_avg': round(prior_avg, 10),
        'raw_relative_volume': round(raw_rv, 6),
        'candle_progress': round(progress, 6),
        'paced_relative_volume': round(paced_rv, 6),
        'expected_formula': 'min(4.0, raw_relative_volume / max(0.10, candle_progress))',
        'scoring_version': PRODUCTION_SCORING_VERSION,
        'production_threshold': float(atlas.CLOUD_FORWARD_MIN_SCORE),
        'research_only': True,
        'live_execution': False,
    }


class WebOnlyHandler(atlas.Handler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/web-mode':
            return self._json({'ok':True, **atlas.WEB_SAFE_MODE, 'research_only':True, 'live_execution':False})
        if parsed.path == '/api/web/volume-diagnostic':
            q = urllib.parse.parse_qs(parsed.query)
            symbol = q.get('symbol', ['BTCUSDT'])[0]
            return self._json(volume_diagnostic(symbol))
        if parsed.path == '/api/research/consensus-tiebreak-shadow':
            q = urllib.parse.parse_qs(parsed.query)
            symbol = q.get('symbol', ['BTCUSDT'])[0]
            try:
                result = atlas.consensus_tiebreak_shadow(symbol)
                return self._json(result, 200 if result.get('ok') else 400)
            except Exception as exc:
                return self._json({
                    'ok': False,
                    'error': f'{type(exc).__name__}: {exc}',
                    'source': atlas.CONSENSUS_TIEBREAK_SHADOW_VERSION,
                    'shadow_only': True,
                    'can_override_production': False,
                    'research_only': True,
                    'live_execution': False,
                }, 500)
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
    print('Production decision UI: ON + autoload', flush=True)
    print(f'Production scoring: {PRODUCTION_SCORING_VERSION}', flush=True)
    print(f'Consensus tie-break shadow: {CONSENSUS_TIEBREAK_SHADOW["version"]}', flush=True)
    print(f'Fourth-vote prospective shadow: {FOURTH_VOTE_SHADOW["version"]}', flush=True)
    print(f'Listening on {port}', flush=True)
    Server(('0.0.0.0',port), WebOnlyHandler).serve_forever(poll_interval=0.5)