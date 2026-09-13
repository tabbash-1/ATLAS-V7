import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

import closed_candle_htf_boot_patch as boot_patch


class FakeAtlas:
    def __init__(self, raw):
        self.raw = raw

    def get_json_fallback(self, urls, family="spot"):
        return self.raw


def _binance_rows(closed_count=70):
    now_ms = int(time.time() * 1000)
    rows = []
    for i in range(closed_count):
        open_ms = now_ms - (closed_count - i + 2) * 3_600_000
        close_ms = open_ms + 3_599_999
        px = 100.0 + i * 0.25
        rows.append([open_ms, str(px), str(px + 1), str(px - 1), str(px + 0.5), "100", close_ms])
    open_ms = now_ms - 1_000
    rows.append([open_ms, "500", "900", "10", "20", "999999", now_ms + 3_599_999])
    return rows


class ClosedCandleHTFTests(unittest.TestCase):
    def _patched_module(self):
        source = Path(__file__).with_name("htf_structural_thesis.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "htf_structural_thesis.py"
            target.write_text(source, encoding="utf-8")
            original_target = boot_patch.TARGET
            try:
                boot_patch.TARGET = target
                boot_patch.apply()
                once = target.read_text(encoding="utf-8")
                boot_patch.apply()
                twice = target.read_text(encoding="utf-8")
                self.assertEqual(once, twice)
                spec = importlib.util.spec_from_file_location("patched_htf_structural_thesis", target)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
            finally:
                boot_patch.TARGET = original_target

    def test_in_progress_candle_is_removed_from_every_timeframe(self):
        module = self._patched_module()
        result = module.build_live_thesis(FakeAtlas(_binance_rows()), "BTCUSDT", proposed_direction="LONG")
        self.assertEqual(result["candle_policy"], "CLOSED_CANDLES_ONLY")
        self.assertFalse(result["in_progress_candles_can_change_authority"])
        for tf in ("1h", "4h", "12h", "1d"):
            quality = result["frame_data_quality"][tf]
            self.assertEqual(quality["dropped_in_progress"], 1)
            self.assertEqual(quality["closed_candles"], 70)
            self.assertLessEqual(quality["last_closed_close_time"], int(time.time() * 1000))

    def test_patch_preserves_4_12h_authority_contract(self):
        module = self._patched_module()
        self.assertEqual(module.PRODUCT_HORIZON, "4-12H")
        self.assertEqual(module.AUTHORITY_TIMEFRAMES, ("12h", "4h"))

    def test_final_entrypoint_self_applies_patches_before_runtime_load(self):
        text = Path(__file__).with_name("cloud_web_only_final.py").read_text(encoding="utf-8")
        self.assertIn("FINAL_ENTRYPOINT_SELF_PATCH_V1", text)
        render_apply = text.index("_apply_render_boot_patch()")
        closed_apply = text.index("_apply_closed_candle_htf_boot_patch()")
        runtime_load = text.index('runpy.run_path(str(BASE / "cloud_web_only.py")')
        self.assertLess(render_apply, runtime_load)
        self.assertLess(closed_apply, runtime_load)


if __name__ == "__main__":
    unittest.main()
