import unittest
from trade_edge_family_validation import summarize

class FamilyValidationTests(unittest.TestCase):
    def rows(self,direction="LONG",regime="BREAKOUT_UP",playbook="BREAKOUT_CONFIRMED_LONG",r=2,n=10):
        return [{"terminal":True,"geometry":{"direction":direction},"regime":regime,"playbook":playbook,"r_multiple":r,"mfe_r":2.1,"mae_r":0.4} for _ in range(n)]

    def test_positive_family(self):
        x=summarize(self.rows())
        self.assertEqual(x["families"][0]["evidence_status"],"HISTORICAL_POSITIVE_EDGE")
        self.assertFalse(x["can_override_production"])

    def test_negative_short_family(self):
        x=summarize(self.rows(direction="SHORT",regime="TREND_DOWN",playbook="TREND_PULLBACK_SHORT",r=-1))
        self.assertEqual(x["families"][0]["evidence_status"],"HISTORICAL_NEGATIVE_EDGE")

    def test_small_sample_not_promoted(self):
        x=summarize(self.rows(n=5))
        self.assertEqual(x["families"][0]["evidence_status"],"INSUFFICIENT_SAMPLE")

if __name__=="__main__": unittest.main()
