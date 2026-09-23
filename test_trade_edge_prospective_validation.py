import unittest
from trade_edge_prospective_validation import evaluate
BASE="2026-09-23T18:00:00+00:00"
def row(i,r=2,d="LONG",p="BREAKOUT_CONFIRMED_LONG"):
 return {"captured_at":f"2026-09-24T{i%20:02d}:00:00+00:00","terminal":True,"r_multiple":r,"regime":"BREAKOUT_UP","playbook":p,"geometry":{"direction":d}}
class T(unittest.TestCase):
 def test_prebaseline_excluded(self):
  old=row(1);old["captured_at"]="2026-09-23T17:00:00+00:00"
  self.assertEqual(evaluate([old,row(2)],BASE,"abc")["overall"]["n"],1)
 def test_proof_needs_sample_and_edge(self):
  rows=[row(i,2 if i<12 else -1) for i in range(20)]
  self.assertEqual(evaluate(rows,BASE,"abc")["proof_status"],"PROSPECTIVE_EDGE_PROVEN")
 def test_losses_fail(self):
  self.assertEqual(evaluate([row(i,-1) for i in range(20)],BASE,"abc")["proof_status"],"COLLECTING_OR_NOT_PROVEN")
 def test_no_production_authority(self):
  self.assertFalse(evaluate([],BASE,"abc")["can_override_production"])
if __name__=="__main__":unittest.main()
