import json
import tempfile
import threading
from pathlib import Path

import trade_path_settlement as tps


def signal_payload(direction='LONG'):
    if direction == 'LONG':
        return {
            'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100.0,
            'champion_take': True, 'final_score': 84, 'rr_tp2': 2.0,
            'support_distance_pct': 1.0, 'resistance_distance_pct': 4.0,
            'execution_decision': 'LONG_CANDIDATE',
        }
    return {
        'symbol': 'BTCUSDT', 'direction': 'SHORT', 'entry': 100.0,
        'champion_take': True, 'final_score': 84, 'rr_tp2': 2.0,
        'support_distance_pct': 4.0, 'resistance_distance_pct': 1.0,
        'execution_decision': 'SHORT_CANDIDATE',
    }


def test_geometry_long_is_deterministic_and_does_not_change_decision():
    p = signal_payload('LONG')
    g = tps.derive_geometry(p)
    assert g['entry'] == 100.0
    assert g['tp2'] == 104.0
    assert g['risk_abs'] == 2.0
    assert g['stop_loss'] == 98.0
    assert g['tp1'] == 102.0
    assert g['rr_tp1'] == 1.0
    assert p['execution_decision'] == 'LONG_CANDIDATE'
    assert p['final_score'] == 84


def test_geometry_short_is_symmetric():
    g = tps.derive_geometry(signal_payload('SHORT'))
    assert g['tp2'] == 96.0
    assert g['stop_loss'] == 102.0
    assert g['tp1'] == 98.0


def test_geometry_unavailable_when_inputs_are_missing():
    p = signal_payload('LONG')
    p['rr_tp2'] = None
    assert tps.derive_geometry(p) is None


def candle(ts, low, high):
    return {'open_time': ts, 'close_time': ts + 299999, 'open': 100, 'high': high, 'low': low, 'close': 100}


def test_path_tp2_wins_and_returns_rr():
    row = {'id': 'x', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100, 'captured_at_ms': 1_000_000, 'champion_take': True}
    geom = {'geometry': tps.derive_geometry(signal_payload('LONG'))}
    rows = [candle(1_000_000, 99, 101), candle(1_300_000, 101, 102.5), candle(1_600_000, 102, 104.2)]
    out = tps.settle_row(row, geom, now_ms=2_000_000, candle_loader=lambda *_: rows)
    assert out['path_outcome'] == 'WIN_TP2'
    assert out['r_multiple'] == 2.0
    assert out['terminal'] is True


def test_path_stop_loss_is_minus_one_r():
    row = {'id': 'x', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100, 'captured_at_ms': 1_000_000, 'champion_take': True}
    geom = {'geometry': tps.derive_geometry(signal_payload('LONG'))}
    rows = [candle(1_000_000, 97.8, 100.5)]
    out = tps.settle_row(row, geom, now_ms=2_000_000, candle_loader=lambda *_: rows)
    assert out['path_outcome'] == 'LOSS'
    assert out['r_multiple'] == -1.0


def test_same_candle_is_not_guessed_when_test_loader_cannot_resolve_order():
    row = {'id': 'x', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100, 'captured_at_ms': 1_000_000, 'champion_take': True}
    geom = {'geometry': tps.derive_geometry(signal_payload('LONG'))}
    rows = [candle(1_000_000, 97.5, 104.5)]
    out = tps.settle_row(row, geom, now_ms=2_000_000, candle_loader=lambda *_: rows)
    assert out['path_outcome'] == 'AMBIGUOUS'
    assert out['r_multiple'] is None


def test_24h_no_hit_expires_at_zero_r():
    start = 1_000_000
    row = {'id': 'x', 'symbol': 'BTCUSDT', 'direction': 'LONG', 'entry': 100, 'captured_at_ms': start, 'champion_take': True}
    geom = {'geometry': tps.derive_geometry(signal_payload('LONG'))}
    rows = [candle(start, 99.2, 100.8)]
    out = tps.settle_row(row, geom, now_ms=start + 24 * 3600000, candle_loader=lambda *_: rows)
    assert out['path_outcome'] == 'EXPIRED'
    assert out['r_multiple'] == 0.0


class FakeCollector:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.DATA = Path(self._tmp.name)
        self.ARCHIVE_LOCK = threading.RLock()
        self.calls = []
        self.seq = 0
    def forward_observe(self, payload):
        self.seq += 1
        self.calls.append(dict(payload))
        return {
            'schema': 'ATLAS_FORWARD_V1', 'id': f'fwd-{self.seq}',
            'captured_at': '2026-08-23T00:00:00+00:00', 'captured_at_ms': 1_000_000 + self.seq,
            'symbol': payload['symbol'], 'direction': payload['direction'], 'entry': payload['entry'],
            'champion_take': payload.get('champion_take', False), 'final_score': payload.get('final_score'),
        }


def test_freezer_persists_separate_exact_id_geometry_archive():
    c = FakeCollector()
    state = tps.install_geometry_freezer(c)
    result = c.forward_observe(signal_payload('LONG'))
    assert result['id'] == 'fwd-1'
    assert state['frozen'] == 1
    rows = tps.read_geometry_archive(c)
    assert len(rows) == 1
    assert rows[0]['forward_observation_id'] == 'fwd-1'
    assert rows[0]['geometry']['stop_loss'] == 98.0
    # The core forward return stays untouched by this independent archive.
    assert 'frozen_trade_geometry' not in result


if __name__ == '__main__':
    test_geometry_long_is_deterministic_and_does_not_change_decision()
    test_geometry_short_is_symmetric()
    test_geometry_unavailable_when_inputs_are_missing()
    test_path_tp2_wins_and_returns_rr()
    test_path_stop_loss_is_minus_one_r()
    test_same_candle_is_not_guessed_when_test_loader_cannot_resolve_order()
    test_24h_no_hit_expires_at_zero_r()
    test_freezer_persists_separate_exact_id_geometry_archive()
    print('trade path settlement tests: ok')
