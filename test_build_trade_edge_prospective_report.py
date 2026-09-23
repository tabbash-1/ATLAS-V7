import json,tempfile,unittest
from pathlib import Path
import build_trade_edge_prospective_report as b
class T(unittest.TestCase):
 def test_baseline_is_frozen(self):
  self.assertEqual(b.BASELINE_COMMIT,"1015a02dc8ab25d812249d55a5ac5e27410e82ed")
  self.assertEqual(b.BASELINE_AT,"2026-09-23T18:00:00+00:00")
if __name__=="__main__":unittest.main()
