import json

import production_opportunity_runtime as runtime


def decision(state='ACTIONABLE', direction='LONG', qualified=True, ready=True):
    return {
        'ok': True, 'symbol': 'BTCUSDT', 'opportunity_state': state,
        'candidate_direction': direction, 'score': 72, 'signal_threshold': 68,
        'production_signal_qualified': qualified, 'execution_ready': ready,
        'geometry_gate': {'qualified': ready},
        'trade_plan': {
            'version': 'TEST', 'status': 'ACTIONABLE' if ready else 'CONDITIONAL',
            'entry_mode': 'NOW' if ready else 'BREAKOUT', 'entry': 100,
            'entry_trigger': 'test trigger', 'stop_loss': 98, 'tp1': 102,
            'tp2': 104, 'rr_tp1': 1, 'rr_tp2': 2,
        },
    }


def test_only_complete_actionable_production_becomes_entry():
    assert runtime.normalize(decision())['action'] == 'ENTER_LONG'
    assert runtime.normalize(decision(direction='SHORT'))['action'] == 'ENTER_SHORT'
    assert runtime.normalize(decision(state='ARMED', ready=False))['action'] == 'WAIT'
    assert runtime.normalize(decision(state='WATCH', qualified=False, ready=False))['action'] == 'WAIT'
    broken = decision()
    broken['trade_plan']['stop_loss'] = None
    assert runtime.normalize(broken)['action'] == 'WAIT'
    inconsistent = decision()
    inconsistent['geometry_gate']['qualified'] = False
    assert runtime.normalize(inconsistent)['action'] == 'WAIT'


class FakeAtlas:
    ON_DEMAND_SYMBOLS = ('BTCUSDT', 'ETHUSDT')

    def __init__(self, tmp_path):
        self.DATA = tmp_path
        self.observed = []

    @staticmethod
    def now_iso():
        return '2026-08-26T22:00:00+00:00'

    def production_decision(self, symbol):
        row = decision(state='ACTIONABLE' if symbol == 'BTCUSDT' else 'ARMED',
                       qualified=True, ready=symbol == 'BTCUSDT')
        row['symbol'] = symbol
        return row

    def forward_observe(self, payload):
        self.observed.append(payload)
        return {'id': 'forward-1'}


def test_scan_records_only_actionable_and_mirrors_explicit_production_flags(tmp_path):
    atlas = FakeAtlas(tmp_path)
    report = runtime.scan(atlas, store=True)
    assert report['summary']['actionable'] == 1
    assert report['summary']['armed'] == 1
    assert report['summary']['paper_trades_stored'] == 1
    assert len(atlas.observed) == 1
    payload = atlas.observed[0]
    assert payload['production_signal_qualified'] is True
    assert payload['execution_ready'] is True
    assert payload['opportunity_state'] == 'ACTIONABLE'
    saved = [json.loads(line) for line in (tmp_path / 'production_paper_trades.jsonl').read_text().splitlines()]
    assert len(saved) == 1 and saved[0]['action'] == 'ENTER_LONG'


def test_stale_snapshot_clears_all_entry_gates(tmp_path):
    status = tmp_path / 'status'
    status.mkdir()
    payload = {
        'captured_at': '2020-01-01T00:00:00+00:00',
        'decisions': {'BTCUSDT': decision()},
    }
    (status / 'atlas-production-latest.json').write_text(json.dumps(payload))
    atlas = FakeAtlas(tmp_path)
    atlas.ROOT = tmp_path
    report = runtime._snapshot_report(atlas)
    row = report['rows'][0]
    assert row['action'] == 'WAIT' and row['opportunity_state'] == 'STALE'
    assert row['production_signal_qualified'] is False
    assert row['geometry_valid'] is False and row['execution_ready'] is False
