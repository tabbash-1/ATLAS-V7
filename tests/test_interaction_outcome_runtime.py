from types import SimpleNamespace

import interaction_outcome_runtime as runtime
import edge_evidence_interaction_protocol as protocol
import edge_evidence_interaction_rules as rules
import edge_evidence_interaction_validator_guard as guard


def joint():
    return {
        'report': {
            'version': 'J',
            'status': 'DESIGN_READ_AVAILABLE',
            'future_interaction_validation_supported': True,
            'horizons_with_sufficient_joint_coverage_h': [1, 4, 12],
        }
    }


def auth():
    p = protocol.build_manifest(joint())
    r = rules.build_manifest(p)
    g = guard.evaluate(p, joint())
    assert g['status'] == 'VALIDATOR_ARMED'
    return p, g, r


def feature_rows(n=60, candidate_n=20):
    profit, micro, vol = [], [], []
    for i in range(n):
        fid = f'F{i:03d}'
        candidate = i < candidate_n
        common = {
            'forward_id': fid,
            'production_signal_qualified': True,
            'research_sample': False,
            'forward_captured_at_ms': 1_000_000 + i,
        }
        profit.append({
            **common,
            'profit_engine': {
                'regime_gate': {
                    'reason': 'REGIME_ALIGNED' if candidate else 'REGIME_NOT_ALIGNED'
                }
            },
        })
        micro.append({
            **common,
            'relation_to_signal': 'ALIGNED' if candidate else 'MIXED_OR_INSUFFICIENT',
        })
        vol.append({
            **common,
            'geometry_fit_by_horizon': {
                str(h): {
                    'target_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'STRETCHED_VS_EMPIRICAL_P80',
                    'stop_fit': 'PLAUSIBLE_VS_EMPIRICAL_P80' if candidate else 'TIGHT_VS_EMPIRICAL_P80',
                }
                for h in (1, 4, 12)
            },
        })
    return profit, micro, vol


def settlements(n=60, candidate_n=20):
    rows = []
    for i in range(n):
        candidate = i < candidate_n
        r = 1.5 if candidate else -1.0
        rows.append({
            'forward_id': f'F{i:03d}',
            'captured_at_ms': 1_000_000 + i,
            'terminal': True,
            'path_outcome': 'WIN_TP2' if r > 0 else 'LOSS',
            'r_multiple': r,
        })
    return rows


def collector():
    decision = lambda symbol: {'symbol': symbol, 'decision': 'WAIT'}
    forward = lambda payload: {'forward_id': 'F'}
    c = SimpleNamespace(
        DATA='.',
        production_decision=decision,
        forward_observe=forward,
        now_iso=lambda: '2026-08-25T00:00:00Z',
    )
    return c, decision, forward


def test_preflight_blocks_before_canonical_loader(monkeypatch):
    p, g, r = auth()
    c, _, _ = collector()
    monkeypatch.setattr(runtime, '_governance', lambda collector: (p, g, r))
    monkeypatch.setattr(runtime, '_read_frozen_rows', lambda sidecars: feature_rows(n=59, candidate_n=20))
    called = {'n': 0}

    def forbidden_loader():
        called['n'] += 1
        raise AssertionError('canonical outcomes must remain unread')

    out = runtime.build_report(c, canonical_loader=forbidden_loader)
    assert out['status'] == 'COLLECTING_PRE_OUTCOME'
    assert out['preflight']['outcome_access_allowed'] is False
    assert out['canonical_outcome_loader_called'] is False
    assert out['outcomes_read'] is False
    assert called['n'] == 0


def test_ready_preflight_calls_canonical_loader_once_and_runs_validator(monkeypatch):
    p, g, r = auth()
    c, _, _ = collector()
    monkeypatch.setattr(runtime, '_governance', lambda collector: (p, g, r))
    monkeypatch.setattr(runtime, '_read_frozen_rows', lambda sidecars: feature_rows(n=60, candidate_n=20))
    called = {'n': 0}

    def canonical_loader():
        called['n'] += 1
        return settlements(), list(range(60)), []

    out = runtime.build_report(c, canonical_loader=canonical_loader)
    assert called['n'] == 1
    assert out['preflight']['outcome_access_allowed'] is True
    assert out['canonical_outcome_loader_called'] is True
    assert out['outcomes_read'] is True
    assert out['canonical_execution_rows'] == 60
    assert out['outcome_validation'] is not None
    assert out['outcome_validation']['rule_search_performed'] is False
    assert out['outcome_validation']['horizon_selection_performed'] is False
    assert out['outcome_validation']['gate_promoted'] is False
    assert out['can_override_production'] is False


def test_stale_guard_blocks_loader_before_frozen_sample_interpretation(monkeypatch):
    p, g, r = auth()
    g = dict(g)
    g['armed_protocol_hash'] = 'stale'
    c, _, _ = collector()
    monkeypatch.setattr(runtime, '_governance', lambda collector: (p, g, r))
    monkeypatch.setattr(runtime, '_read_frozen_rows', lambda sidecars: feature_rows(n=60, candidate_n=20))
    called = {'n': 0}

    def forbidden_loader():
        called['n'] += 1
        return settlements(), [], []

    out = runtime.build_report(c, canonical_loader=forbidden_loader)
    assert out['status'] == 'BLOCKED'
    assert 'GUARD_PROTOCOL_HASH_MISMATCH' in out['blockers']
    assert out['canonical_outcome_loader_called'] is False
    assert called['n'] == 0


def test_install_is_background_only_idempotent_and_preserves_runtime_paths(monkeypatch):
    c, decision, forward = collector()

    class NoStartThread:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            return None

    monkeypatch.setattr(runtime.threading, 'Thread', NoStartThread)
    monkeypatch.setattr(runtime, '_governance', lambda collector: (None, None, None))

    first = runtime.install(c)
    assert first['background_only'] is True
    assert first['shadow_only'] is True
    assert first['research_only'] is True
    assert first['wraps_production_decision'] is False
    assert first['wraps_forward_observe'] is False
    assert first['can_override_production'] is False
    assert first['gate_promoted'] is False
    assert c.production_decision is decision
    assert c.forward_observe is forward

    second = runtime.install(c)
    assert second is first
    assert c.production_decision is decision
    assert c.forward_observe is forward


def test_refresh_failure_is_isolated_to_unavailable_research_state(monkeypatch):
    c, decision, forward = collector()

    class NoStartThread:
        def __init__(self, *args, **kwargs):
            pass
        def start(self):
            return None

    monkeypatch.setattr(runtime.threading, 'Thread', NoStartThread)
    monkeypatch.setattr(runtime, '_governance', lambda collector: (None, None, None))
    state = runtime.install(c)
    monkeypatch.setattr(runtime, 'build_report', lambda collector: (_ for _ in ()).throw(RuntimeError('boom')))
    result = c.interaction_outcome_refresh()
    assert result is None
    assert state['report']['status'] == 'UNAVAILABLE'
    assert state['report']['outcomes_read'] is False
    assert state['report']['can_override_production'] is False
    assert state['report']['gate_promoted'] is False
    assert 'INTERACTION_OUTCOME_RUNTIME_REFRESH_ERROR' in state['report']['blockers']
    assert c.production_decision is decision
    assert c.forward_observe is forward
