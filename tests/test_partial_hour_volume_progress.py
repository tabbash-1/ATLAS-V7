import unittest

from production_signal_scoring import candle_progress, paced_relative_volume


class PartialHourVolumeProgressTests(unittest.TestCase):
    def test_live_kline_time_key_is_used(self):
        # collector_server._spot_klines exposes Binance open time as `time`.
        now_ms = 1_700_000_600_000
        row = {'time': 1_700_000_000_000}
        self.assertAlmostEqual(candle_progress(row, now_ms), 600_000 / 3_600_000, places=6)

    def test_open_time_key_remains_supported(self):
        now_ms = 1_700_000_900_000
        row = {'open_time': 1_700_000_000_000}
        self.assertAlmostEqual(candle_progress(row, now_ms), 0.25, places=6)

    def test_completed_candle_is_unchanged(self):
        now_ms = 1_700_007_200_000
        row = {'time': 1_700_000_000_000}
        self.assertEqual(candle_progress(row, now_ms), 1.0)
        self.assertEqual(paced_relative_volume(0.8, 1.0), 0.8)

    def test_early_candle_floor_prevents_explosion(self):
        now_ms = 1_700_000_060_000
        row = {'time': 1_700_000_000_000}
        # progress is floored at 10%; a raw 0.05 RV becomes 0.5 paced RV.
        self.assertEqual(candle_progress(row, now_ms), 0.10)
        self.assertEqual(paced_relative_volume(0.05, candle_progress(row, now_ms)), 0.5)


if __name__ == '__main__':
    unittest.main()
