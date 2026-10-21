"""Regression contracts for research-only profitability snapshot publishing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/atlas-profitability-shadow-web.yml"
SCRIPT = ROOT / "profitability_shadow_snapshot.py"


class ProfitabilityShadowWorkflowTests(unittest.TestCase):
    def test_retries_non_fast_forward_without_force_push(self):
        y = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("for attempt in 1 2 3 4 5", y)
        self.assertIn("git fetch origin main", y)
        self.assertIn("git rebase origin/main", y)
        self.assertIn("git push origin HEAD:main", y)
        self.assertIn("exit 1", y)
        self.assertNotIn("--force", y)

    def test_research_only_file_and_no_production_gate_write(self):
        y = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("git add status/profitability-shadow-latest.json", y)
        self.assertNotIn("git add -A", y)
        self.assertNotIn("git add .", y)
        self.assertNotIn("FINAL_TRADE_GATE", y)
        self.assertIn("if: github.event_name != 'pull_request'", y)

    def test_pr_runs_regression_without_publishing(self):
        y = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request:", y)
        self.assertIn("python tests/test_profitability_shadow_workflow.py", y)
        self.assertIn("python profitability_shadow_snapshot.py", y)

    def test_payload_is_research_only(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"research_only":True', src)
        self.assertIn('"can_override_production":False', src)
        self.assertIn('"live_execution":False', src)


if __name__ == "__main__":
    unittest.main()
