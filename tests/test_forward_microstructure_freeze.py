#!/usr/bin/env python3
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import forward_microstructure_freeze_runtime as freeze


class FakeCollector:
    def __init__(self):
        self.rows = [
            {'symbol':'BTCUSDT','captured_at_ms':900_000,'funding_rate':0.001,'open_interest':100,'oi_change_pct':1.0,'taker_ratio':1.2,'orderbook_imbalance':0.2},
            {'symbol':'BTCUSDT','captured_at_ms':1_000_001,'funding_rate':0.5,'open_interest':999,'oi_change_pct':99,'taker_ratio':9,'orderbook_imbalance':0.99},
        ]
    def read_all(self):
        return list(self.rows)


def main():
    collector = FakeCollector()
    row = {'schema':'ATLAS_FORWARD_V1','captured_at_ms':1_000_000,'symbol':'BTCUSDT','direction':'LONG','entry':100}
    out = freeze.enrich_row(collector, row)
    assert out['microstructure_freeze_schema'] == freeze.VERSION
    assert out['microstructure_source_rows_prior_only_at_entry'] == 1, out
    assert out['microstructure_outcome_known_at_entry'] is False
    assert out['microstructure_future_data_allowed_at_entry'] is False
    assert out['microstructure_can_override_production'] is False
    assert 'microstructure_relation_at_entry' in out
    assert 'forward_return_pct' not in out
    print('forward microstructure freeze tests: OK')


if __name__ == '__main__':
    main()
