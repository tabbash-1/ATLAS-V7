import unittest
from datetime import datetime, timedelta, timezone

from scored_wait_attribution_audit import (
    THRESHOLD,
    audit,
    corrected_score,
    independent_12h,
)


def row(ts, *, symbol="BTCUSDT", score=64, raw_score=64, rv=0.2,
        obstacle=-4, obstacle_reason="CLOSE_PRIOR_STRUCTURE",
        futures=0, futures_reason="NOT_AVAILABLE",
        rs=0, rs_reason="NEUTRAL", votes=3,
        ret12=1.0, ret24=1.5,
        version="PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE"):
    return {
        "symbol": symbol,
        "wait_at": ts.isoformat(),
        "wait_price": 100,
        "candidate_direction": "LONG",
        "reason": "SCORE_BELOW_SIGNAL_THRESHOLD",
        "score": score,
        "threshold": 68,
        "decision_context": {
            "scoring_version": version,
            "relative_volume": rv,
            "direction_votes": votes,
        },
        "score_attribution": {
            "raw_score": raw_score,
            "final_score": score,
            "volume_bonus": 0,
            "obstacle_adjustment": obstacle,
            "obstacle_reason": obstacle_reason,
            "futures_adjustment": futures,
            "futures_reason": futures_reason,
            "relative_strength_adjustment": rs,
            "relative_strength_reason": rs_reason,
        },
        "horizons": {
            "1h": {"directional_return_pct": 0.2},
            "3h": {"directional_return_pct": 0.5},
            "12h": {"directional_return_pct": ret12},
            "24h": {"directional_return_pct": ret24},
        },
    }


class ScoredWaitAttributionAuditTests(unittest.TestCase):
    def test_partial_hour_volume_replay_can_recover_threshold(self):
        # 15 minutes into hour => progress .25. Raw RV .30 paces to 1.20,
        # restoring +2 V6 volume points to a raw score of 67.
        ts = datetime(2026, 8, 28, 10, 15, tzinfo=timezone.utc)
        r = row(ts, score=67, raw_score=67, rv=0.30, obstacle=0,
                obstacle_reason="ACCEPTABLE_PRIOR_STRUCTURE")
        got = corrected_score(r)
        self.assertEqual(got["score"], 69)
        self.assertAlmostEqual(got["volume_delta"], 2.0, places=6)
        self.assertGreaterEqual(got["paced_rv"], 1.19)

    def test_post_fix_score_is_not_replayed_again(self):
        ts = datetime(2026, 8, 28, 10, 15, tzinfo=timezone.utc)
        r = row(
            ts, score=65, raw_score=65, rv=1.1,
            version="PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE+PARTIAL_VOLUME_TIME_FIX_V1",
        )
        got = corrected_score(r)
        self.assertEqual(got["score"], 65)
        self.assertEqual(got["volume_delta"], 0.0)
        self.assertTrue(got["post_fix"])

    def test_independent_12h_dedupes_correlated_rows(self):
        t0 = datetime(2026, 8, 28, 0, 0, tzinfo=timezone.utc)
        rows = [row(t0), row(t0 + timedelta(hours=2)), row(t0 + timedelta(hours=13))]
        eps = independent_12h(rows)
        self.assertEqual(len(eps), 2)

    def test_single_component_counterfactual_does_not_change_production(self):
        t0 = datetime(2026, 8, 26, 12, 50, tzinfo=timezone.utc)
        records = []
        # Eight independent CLOSE-penalty episodes. Stored score 64 + removing
        # only the -4 obstacle penalty would cross exactly to 68.
        for i in range(8):
            records.append(row(
                t0 + timedelta(hours=13 * i),
                symbol=f"S{i % 4}USDT",
                score=64,
                raw_score=64,
                rv=0.2,
                obstacle=-4,
                obstacle_reason="CLOSE_PRIOR_STRUCTURE",
                ret12=0.5 + i * 0.01,
                ret24=0.8 + i * 0.01,
                version="PROD_SIGNAL_SCORING_V6_BREAKOUT_AWARE+PARTIAL_VOLUME_TIME_FIX_V1",
            ))
        report = audit({"records": records})
        cf = report["single_component_counterfactuals"]["REMOVE_CLOSE_OBSTACLE_PENALTY"]
        self.assertGreaterEqual(cf["hourly_crossings"], 1)
        self.assertEqual(report["guardrails"]["production_threshold"], THRESHOLD)
        self.assertFalse(report["guardrails"]["production_threshold_changed"])
        self.assertFalse(report["guardrails"]["production_score_changed"])
        self.assertFalse(report["guardrails"]["auto_promotion_enabled"])
        self.assertFalse(report["guardrails"]["live_execution"])


if __name__ == "__main__":
    unittest.main()
