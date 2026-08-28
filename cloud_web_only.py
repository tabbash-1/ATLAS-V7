#!/usr/bin/env python3
"""Ultra-light ATLAS Render web runtime.

Purpose: keep the public site and on-demand Production decision endpoints alive
inside a small Render instance. No background collectors, warm-up scans, cloud
forward loops, research replays, opportunity scans, reliability warm-up, or
profit-engine background jobs are started here.

Scheduled research remains on GitHub Actions. Production threshold is unchanged.
"""
import os
from http.server import ThreadingHTTPServer

os.environ.setdefault('ATLAS_CLOUD_FORWARD_ENABLED','0')
os.environ.setdefault('ATLAS_CLOUD_FORWARD_MIN_SCORE','68')

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
from production_signal_scoring import install as install_scoring
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

# Expose explicit web-safe mode for UI/ops diagnostics.
atlas.WEB_SAFE_MODE = {
    'enabled': True,
    'background_workers': False,
    'cloud_forward_in_web_process': False,
    'production_threshold': float(atlas.CLOUD_FORWARD_MIN_SCORE),
    'research_execution_location': 'GITHUB_ACTIONS',
}

class WebOnlyHandler(atlas.Handler):
    def do_GET(self):
        if self.path.split('?',1)[0] == '/api/web-mode':
            return self._json({'ok':True, **atlas.WEB_SAFE_MODE, 'research_only':True, 'live_execution':False})
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
    print(f'Listening on {port}', flush=True)
    Server(('0.0.0.0',port), WebOnlyHandler).serve_forever(poll_interval=0.5)
