import json
from pathlib import Path
from types import SimpleNamespace

import volatility_runtime


class FakeThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return None


def make_collector(tmp_path, *, forward_result=None):
    if forward_result is None:
        forward_result = {'id': 'FWD-V1', 'captured_at_ms': 1234567890}
    calls = {'forward': 0, 'klines': 0}

    def production_decision(symbol):
        return {
            'ok': True,
            'symbol': symbol,
            'candidate_direction': 'LONG',
            'production_signal_qualified': True,
            'actionable_decision': 'LONG',
            'score': 73,
            'entry': 100.0,
            'stop_loss': 98.0,
            'take_profit': 104.0,
            'risk_reward': 2.0,
        }

    def forward_observe(payload):
        calls['forward'] += 1
        return dict(forward_result) if forward_result is not None else None

    def spot_klines(symbol):
        calls['klines'] += 1
        raise AssertionError('decision path must not fetch klines')

    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        ON_DEMAND_SYMBOLS=('BTCUSDT',),
        production_decision=production_decision,
        forward_observe=forward_observe,
        _spot_klines=spot_klines,
        now_iso=lambda: '2026-08-25T17:30:00+00:00',
    )
    collector._calls = calls
    return collector


def install_without_threads(monkeypatch, collector):
    monkeypatch.setattr(volatility_runtime.threading, 'Thread', FakeThread)
    return volatility_runtime.install(collector)


def ready_forecast():
    horizons = {}
    for h, p80 in ((1, 1.0), (4, 2.0), (12, 3.5)):
        horizons[str(h)] = {
            'status': 'READY',
            'horizon_h': float(h),
            'empirical_abs_move_pct': {'p50': p80 * .6, 'p80': p80, 'p95': p80 * 1.4},
        }
    return {
        'version': 'TEST_FORECAST',
        'symbol': 'BTCUSDT',
        'status': 'READY',
        'horizons': horizons,
        'volatility_regime': 'VOL_NORMAL',
        'probability_calibrated': False,
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
    }


def read_sidecar(tmp_path):
    path = Path(tmp_path) / 'volatility_forecast_observations.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_decision_uses_cache_only_and_never_mutates_production(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    state['forecast_by_symbol']['BTCUSDT'] = ready_forecast()

    decision = collector.production_decision('BTCUSDT')
    assert collector._calls['klines'] == 0
    assert decision['actionable_decision'] == 'LONG'
    assert decision['production_signal_qualified'] is True
    assert decision['entry'] == 100.0
    assert decision['stop_loss'] == 98.0
    assert decision['take_profit'] == 104.0
    shadow = decision['volatility_shadow']
    assert shadow['can_override_production'] is False
    assert shadow['gate_promoted'] is False
    assert shadow['production_decision_unchanged'] is True
    assert set(shadow['geometry_fit_by_horizon']) == {'1', '4', '12'}


def test_stretched_or_tight_fit_cannot_block_production(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    forecast = ready_forecast()
    forecast['horizons']['1']['empirical_abs_move_pct']['p80'] = 0.5
    state['forecast_by_symbol']['BTCUSDT'] = forecast

    decision = collector.production_decision('BTCUSDT')
    assert decision['actionable_decision'] == 'LONG'
    assert decision['volatility_shadow']['geometry_fit_by_horizon']['1']['target_fit'] == 'STRETCHED_VS_EMPIRICAL_P80'
    assert decision['volatility_shadow']['can_override_production'] is False


def test_research_forward_is_never_frozen(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    collector.forward_observe({
        'symbol': 'BTCUSDT', 'direction': 'LONG',
        'production_signal_qualified': False, 'research_sample': True,
    })
    assert read_sidecar(tmp_path) == []
    assert state['research_observations_included'] == 0
    assert state['frozen_signal_observations'] == 0


def test_new_production_forward_freezes_cached_forecast(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    state['forecast_by_symbol']['BTCUSDT'] = ready_forecast()

    result = collector.forward_observe({
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100.0,
        'structural_target': 104.0,
        'rr_tp2': 2.0,
        'final_score': 73,
        'production_signal_qualified': True,
    })
    rows = read_sidecar(tmp_path)
    assert result['id'] == 'FWD-V1'
    assert len(rows) == 1
    row = rows[0]
    assert row['schema'] == 'ATLAS_VOLATILITY_FORECAST_OBSERVATION_V1'
    assert row['forward_id'] == 'FWD-V1'
    assert row['derived_stop_loss'] == 98.0
    assert row['forecast']['version'] == 'TEST_FORECAST'
    assert row['chosen_trade_horizon_assumed'] is False
    assert row['outcome_known_at_capture'] is False
    assert row['can_override_production'] is False
    assert state['frozen_signal_observations'] == 1


def test_dedup_without_forward_id_does_not_freeze(monkeypatch, tmp_path):
    collector = make_collector(tmp_path, forward_result={})
    state = install_without_threads(monkeypatch, collector)
    state['forecast_by_symbol']['BTCUSDT'] = ready_forecast()
    result = collector.forward_observe({
        'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100,
        'structural_target': 104, 'rr_tp2': 2,
        'production_signal_qualified': True,
    })
    assert result == {}
    assert read_sidecar(tmp_path) == []
    assert state['frozen_signal_observations'] == 0


def test_background_refresh_failure_is_isolated(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    out = collector.volatility_refresh_forecasts()
    assert out['BTCUSDT']['status'] == 'INSUFFICIENT'
    assert out['BTCUSDT']['reason'] == 'VOLATILITY_FORECAST_REFRESH_FAILED'
    assert state['last_forecast_errors']['BTCUSDT']
    decision = collector.production_decision('BTCUSDT')
    assert decision['actionable_decision'] == 'LONG'
    assert decision['volatility_shadow']['can_override_production'] is False
