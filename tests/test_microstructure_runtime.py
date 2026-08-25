import json
from pathlib import Path
from types import SimpleNamespace

import microstructure_runtime


class FakeThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return None


def make_collector(tmp_path, *, forward_result=None):
    if forward_result is None:
        forward_result = {'id': 'FWD-1', 'captured_at_ms': 1234567890}

    calls = {'forward': 0}

    def production_decision(symbol):
        return {
            'ok': True,
            'symbol': symbol,
            'candidate_direction': 'LONG',
            'production_signal_qualified': True,
            'actionable_decision': 'LONG',
            'final_score': 72,
            'entry': 100.0,
            'stop_loss': 98.0,
            'risk_reward': 2.2,
        }

    def forward_observe(payload):
        calls['forward'] += 1
        return dict(forward_result) if forward_result is not None else None

    collector = SimpleNamespace(
        DATA=Path(tmp_path),
        ON_DEMAND_SYMBOLS=('BTCUSDT',),
        CLOUD_FORWARD_MIN_SCORE=68,
        production_decision=production_decision,
        forward_observe=forward_observe,
        read_all=lambda: [],
        read_forward=lambda: [],
        now_iso=lambda: '2026-08-25T17:00:00+00:00',
    )
    collector._calls = calls
    return collector


def install_without_threads(monkeypatch, collector):
    monkeypatch.setattr(microstructure_runtime.threading, 'Thread', FakeThread)
    return microstructure_runtime.install(collector)


def read_sidecar(tmp_path):
    path = Path(tmp_path) / 'microstructure_observations.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_decision_core_is_unchanged_and_shadow_cannot_override(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    install_without_threads(monkeypatch, collector)

    before = {
        'production_signal_qualified': True,
        'actionable_decision': 'LONG',
        'final_score': 72,
        'entry': 100.0,
        'stop_loss': 98.0,
        'risk_reward': 2.2,
    }
    decision = collector.production_decision('BTCUSDT')

    for key, value in before.items():
        assert decision[key] == value
    shadow = decision['microstructure_shadow']
    assert shadow['can_override_production'] is False
    assert shadow['gate_promoted'] is False
    assert shadow['production_decision_unchanged'] is True
    assert shadow['relation_to_candidate'] == 'MIXED_OR_INSUFFICIENT'


def test_research_payload_never_enters_microstructure_sidecar(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)

    result = collector.forward_observe({
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'production_signal_qualified': False,
        'research_sample': True,
    })

    assert result['id'] == 'FWD-1'
    assert collector._calls['forward'] == 1
    assert read_sidecar(tmp_path) == []
    assert state['research_observations_included'] == 0
    assert state['frozen_signal_observations'] == 0


def test_new_production_forward_freezes_exactly_one_observation(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)

    result = collector.forward_observe({
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry': 100,
        'final_score': 72,
        'signal_threshold': 68,
        'production_signal_qualified': True,
    })

    rows = read_sidecar(tmp_path)
    assert result['id'] == 'FWD-1'
    assert len(rows) == 1
    row = rows[0]
    assert row['schema'] == 'ATLAS_MICROSTRUCTURE_OBSERVATION_V1'
    assert row['forward_id'] == 'FWD-1'
    assert row['production_signal_qualified'] is True
    assert row['research_sample'] is False
    assert row['outcome_known_at_capture'] is False
    assert row['can_override_production'] is False
    assert row['gate_promoted'] is False
    assert row['microstructure_memory']['consensus'] == 'INSUFFICIENT'
    assert state['frozen_signal_observations'] == 1


def test_dedup_without_forward_id_does_not_create_sidecar(monkeypatch, tmp_path):
    collector = make_collector(tmp_path, forward_result={})
    state = install_without_threads(monkeypatch, collector)

    result = collector.forward_observe({
        'symbol': 'BTCUSDT',
        'direction': 'SHORT',
        'production_signal_qualified': True,
    })

    assert result == {}
    assert read_sidecar(tmp_path) == []
    assert state['frozen_signal_observations'] == 0


def test_opposed_cached_flow_is_observe_only(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)
    state['memory_by_symbol']['BTCUSDT'] = {
        'version': 'TEST',
        'symbol': 'BTCUSDT',
        'consensus': 'BEARISH_FLOW',
        'ready_windows': 3,
        'windows': {},
        'research_only': True,
        'shadow_only': True,
        'can_override_production': False,
    }

    decision = collector.production_decision('BTCUSDT')
    assert decision['actionable_decision'] == 'LONG'
    assert decision['production_signal_qualified'] is True
    assert decision['final_score'] == 72
    assert decision['microstructure_shadow']['relation_to_candidate'] == 'OPPOSED_OR_CROWDED'
    assert decision['microstructure_shadow']['can_override_production'] is False


def test_walkforward_failure_is_isolated_from_production(monkeypatch, tmp_path):
    collector = make_collector(tmp_path)
    state = install_without_threads(monkeypatch, collector)

    monkeypatch.setattr(
        microstructure_runtime,
        'build_walkforward_report',
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('boom')),
    )
    assert collector.microstructure_refresh_walkforward() is None
    assert state['walk_forward_report']['status'] == 'UNAVAILABLE'
    assert state['walk_forward_report']['can_override_production'] is False

    decision = collector.production_decision('BTCUSDT')
    assert decision['actionable_decision'] == 'LONG'
    assert decision['production_signal_qualified'] is True
