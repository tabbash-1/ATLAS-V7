import unittest

from trade_edge_engine import assess


def base_row():
    return {
        "product_direction": "LONG",
        "entry_confirmation_direction": "LONG",
        "direction_alignment": "ALIGNED",
        "regime": "TREND_UP",
        "playbook": "MARKET_CONTINUATION_LONG",
        "htf_core_geometry": {"ready": True, "rr_tp2": 2.0},
        "trade_plan": {"rr_tp2": 2.0},
    }


class TradeEdgeEngineTests(unittest.TestCase):
    def test_mature_long_family_can_be_edge_candidate(self):
        x = assess(base_row())
        self.assertEqual(x["stage"], "EDGE_CANDIDATE")
        self.assertGreater(x["expected_value_r_before_costs"], 0)
        self.assertFalse(x["can_override_production"])

    def test_direction_without_entry_waits(self):
        row = base_row()
        row["entry_confirmation_direction"] = None
        self.assertEqual(assess(row)["stage"], "WAIT_TRIGGER")

    def test_geometry_is_independent_from_direction(self):
        row = base_row()
        row["htf_core_geometry"] = {"ready": False, "rr_tp2": 2.0}
        self.assertEqual(assess(row)["stage"], "WAIT_GEOMETRY")

    def test_short_is_not_invented_from_long_evidence(self):
        row = base_row()
        row.update({
            "product_direction": "SHORT",
            "entry_confirmation_direction": "SHORT",
            "regime": "TREND_DOWN",
            "playbook": "MARKET_CONTINUATION_SHORT",
        })
        x = assess(row)
        self.assertEqual(x["stage"], "RESEARCH_ONLY")
        self.assertIsNone(x["empirical_prior"])

    def test_directional_prior_is_not_mislabeled_as_tp_probability(self):
        x = assess(base_row())
        self.assertIn("NOT_TP_BEFORE_SL", x["probability_semantics"])


if __name__ == "__main__":
    unittest.main()
