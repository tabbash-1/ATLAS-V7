import profit_engine_runtime as runtime


class Collector:
    def __init__(self):
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

    @staticmethod
    def now_iso():
        return '2026-08-25T00:00:00+00:00'

    @staticmethod
    def read_forward():
        return []


def test_shadow_does_not_override_production(monkeypatch):
    collector = Collector()
    monkeypatch.setattr(runtime.threading.Thread, 'start', lambda self: None)
    state = runtime.install(collector)
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


def test_wilson_interval_is_bounded():
    low, high = runtime._wilson_interval(70, 100)
    assert 0 <= low <= .70 <= high <= 1
