# ATLAS Phase 3 — Challenger Forward Evidence

Status: research/shadow only.

The Challenger evaluates the narrow `4H_DIRECTIONAL_12H_NEUTRAL + HTF_CONFLICT` hypothesis using immutable post-V2 WAIT outcomes. It does not alter Production decisions, score, threshold 68, risk, stops, targets, or execution.

The workflow rebuilds the evidence report whenever the canonical WAIT observatory report changes and every four hours. Reports are uploaded as immutable GitHub Actions artifacts for review.

A sample size of 30 matured 12H observations only opens a promotion review. It never authorizes promotion. Any future Production proposal requires a separate PR with Champion-vs-Challenger forward evidence, direction/asset breakdown, expectancy/robustness review, regression tests, and explicit proof that no look-ahead data was introduced.
