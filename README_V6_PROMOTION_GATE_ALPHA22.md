# ATLAS V6 Promotion Gate — Alpha 22

Research-only. Live execution disabled.

## Purpose
Provide one auditable gate for moving any learned or adaptive feature beyond Shadow research.

## Adaptive promotion policy
A controlled-promotion candidate must pass ALL:
- Data Quality >= 85 and HEALTHY
- Drift status = STABLE
- >= 80 usable matured adaptive observations
- weighted expectancy improvement >= 0.03 percentage points
- risk-adjusted improvement >= 0.05
- adaptive drawdown may not worsen by more than 0.10 proxy units
- evidence from at least 2 market regimes

## Learned-rule promotion policy
Each rule must pass:
- Discovery N >= 60
- Validation tagged N >= 20
- harmful pattern remains stable out of sample
- filtering improves out-of-sample performance
- global Data Quality = HEALTHY
- global Drift = STABLE

## Critical behavior
Every criterion is shown as PASS / FAIL with current value and threshold.

Passing the gate does NOT activate the feature.
It only changes the next allowed research stage to:
`CONTROLLED_CANARY_ONLY`

There is still:
- no automatic activation
- no change to Final Score
- no change to Portfolio Risk
- no exchange execution

## API
- GET `/api/promotion-gate?horizon=24`
