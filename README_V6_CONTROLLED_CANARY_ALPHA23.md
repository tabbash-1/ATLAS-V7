# ATLAS V6 Controlled Canary — Alpha 23

Research-only. Live execution disabled.

## Purpose
Test a Promotion-Gate-approved feature on a small deterministic Shadow cohort before any broader promotion.

## Assignment
- 15% Canary
- 85% Control
- deterministic hash assignment frozen at observation time
- only observations recorded while the relevant feature is Promotion-Gate eligible can enter Canary
- later learning cannot rewrite cohort assignment

## Current Canary feature
Adaptive sizing.

Control:
- fixed risk sizing

Canary:
- adaptive shadow sizing frozen at entry

## Evaluation
ATLAS calculates:
- Control weighted return metrics
- Canary weighted return metrics
- Canary fixed-size counterfactual on the exact same Canary observations
- cohort delta
- paired delta
- risk-adjusted deltas
- paired drawdown worsening

The paired comparison is important because it compares adaptive vs fixed sizing on the same Canary market observations.

## Minimums before a verdict
- Canary N >= 25
- Control N >= 75
- paired Canary N >= 25

## Pass criteria
- paired average improvement >= 0.02 percentage points
- paired risk-adjusted improvement >= 0.03
- paired drawdown worsening <= 0.10 proxy units

Possible verdicts:
- COLLECTING
- CANARY_PASS
- CANARY_FAIL
- CANARY_INCONCLUSIVE
- CANARY_PASS_BUT_SAFETY_HOLD

If Drift = EDGE_RISK or Data Quality = DEGRADED, a passing result is held for safety review.

## Critical guardrails
- no automatic cohort expansion
- no automatic activation
- no Portfolio Risk change
- no Final Score change
- no exchange orders

A Canary pass only allows:
`MANUAL_REVIEW_FOR_LARGER_SHADOW_CANARY`
