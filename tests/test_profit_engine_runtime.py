import json
from pathlib import Path

import profit_engine_runtime as runtime


class Collector:
    CLOUD_FORWARD_MIN_SCORE = 68
    ON_DEMAND_SYMBOLS = ('BTCUSDT',)
    UA = 'test'

    def __init__(self, data_dir=None):
        self.DATA = Path(data_dir or '.')
        self._forward_calls = 0
        self._dedup = False
        self.production_decision = lambda symbol: {
            'ok': True,
            'symbol': symbol,
            'production_signal_qualified': True,
            'candidate_direction': 'LONG',
            'actionable_decision': 'LONG',
            'regime': 'TREND_UP',
            'entry': 100.0,
            'stop_loss': 98.0,
            'risk_reward': 1.8,
        }
        self.forward_observe = self._forward_observe

    def _forward_observe(self, payload):
        self._forward_calls += 1
        if self._dedup:
            return {'stored': False, 'reason': 'DEDUP_WINDOW', 'existing_id': 'old-id'}
        return {
            'id': f'fwd-{self._forward_calls}',
            'captured_at_ms': 123456789,
            'symbol': payload.get('symbol'),
            'direction': payload.get('direction'),
        }

    @staticmethod
    def now_iso():
        return '2026-08-25T00:00:00+00:00'

    @staticmethod
    def read_forward():
        return []


def _install_without_threads(monkeypatch, tmp_path):
    collector = Collector(tmp_path)
    monkeypatch.setattr(runtime.threading.Thread, 'start', lambda self: None)
    state = runtime.install(collector)
    return collector, state


def _signal_payload():
    return {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100.0,
        'final_score': 72,
        'signal_threshold': 68,
        'production_signal_qualified': True,
        'structural_target': 103.6,
        'rr_tp2': 1.8,
    }


def test_shadow_does_not_override_production(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    out = collector.production_decision('BTCUSDT')
    assert out['actionable_decision'] == 'LONG'
    assert out['production_signal_qualified'] is True
    shadow = out['profit_engine_shadow']
    assert shadow['shadow_only'] is True
    assert shadow['can_override_production'] is False
    assert shadow['production_decision_unchanged'] is True
    assert shadow['profit_ready'] is False
    assert 'CALIBRATION_WARMUP' in shadow['blockers']
    assert 'EXECUTION_COST_MODEL_UNAVAILABLE' in shadow['blockers']
    assert state['shadow_only'] is True
    assert state['walk_forward_report']['status'] == 'COLLECTING'
    assert state['walk_forward_report']['can_override_production'] is False


def test_production_signal_freezes_pre_outcome_evidence(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    result = collector.forward_observe(_signal_payload())
    assert result['id'] == 'fwd-1'

    archive = tmp_path / 'profit_engine_observations.jsonl'
    lines = archive.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row['forward_id'] == 'fwd-1'
    assert row['production_signal_qualified'] is True
    assert row['research_sample'] is False
    assert row['research_samples_included'] is False
    assert row['outcome_known_at_capture'] is False
    assert row['derived_stop_loss'] == 98.0
    assert row['shadow_only'] is True
    assert row['can_override_production'] is False
    assert state['frozen_signal_observations'] == 1
    assert state['research_observations_included'] == 0


def test_research_row_never_enters_profit_observation_archive(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    payload = _signal_payload()
    payload['production_signal_qualified'] = False
    payload['research_sampling_lane'] = True
    result = collector.forward_observe(payload)
    assert result['id'] == 'fwd-1'
    archive = tmp_path / 'profit_engine_observations.jsonl'
    assert not archive.exists()
    assert state['frozen_signal_observations'] == 0
    assert state['research_observations_included'] == 0


def test_dedup_does_not_duplicate_profit_observation(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    collector._dedup = True
    result = collector.forward_observe(_signal_payload())
    assert result['stored'] is False
    archive = tmp_path / 'profit_engine_observations.jsonl'
    assert not archive.exists()
    assert state['frozen_signal_observations'] == 0


def test_walkforward_refresh_updates_state_without_touching_production(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    before = collector.production_decision('BTCUSDT')['actionable_decision']

    fake_report = {
        'version': 'TEST_WF',
        'status': 'VALIDATION_READ_AVAILABLE',
        'improves_production_expectancy': True,
        'blockers': [],
        'settled_joined': 60,
        'profit_ready_settled': 20,
        'research_samples_included': False,
        'shadow_only': True,
        'can_override_production': False,
    }
    monkeypatch.setattr(runtime, 'build_walkforward_report', lambda collector_arg, path_arg: dict(fake_report))
    refreshed = collector.profit_engine_refresh_walkforward()

    assert refreshed['improves_production_expectancy'] is True
    assert state['walk_forward_report']['status'] == 'VALIDATION_READ_AVAILABLE'
    assert state['walkforward_refreshes'] == 1
    assert state['last_walkforward_error'] is None
    after = collector.production_decision('BTCUSDT')['actionable_decision']
    assert before == 'LONG' and after == 'LONG'


def test_walkforward_error_fails_closed(monkeypatch, tmp_path):
    collector, state = _install_without_threads(monkeypatch, tmp_path)
    monkeypatch.setattr(runtime, 'build_walkforward_report', lambda collector_arg, path_arg: (_ for _ in ()).throw(RuntimeError('boom')))
    refreshed = collector.profit_engine_refresh_walkforward()
    assert refreshed is None
    assert state['walk_forward_report']['status'] == 'UNAVAILABLE'
    assert state['walk_forward_report']['improves_production_expectancy'] is False
    assert 'WALK_FORWARD_REFRESH_ERROR' in state['walk_forward_report']['blockers']


def test_wilson_interval_is_bounded():
    low, high = runtime._wilson_interval(70, 100)
    assert 0 <= low <= .70 <= high <= 1
