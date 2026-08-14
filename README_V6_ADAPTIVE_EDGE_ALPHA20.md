# ATLAS V6 Adaptive Edge Allocation — Alpha 20

Research-only. Live execution disabled.

## Purpose
Learn that the same setup can have very different expectancy in different market regimes.

Alpha 20 builds evidence by:
- Market Regime
- Primary Playbook
- 24h directional forward outcome

## Method
For each Regime × Playbook group:
- lifetime N / hit rate / average return
- recent up-to-20 observations
- sample-size shrinkage toward the global baseline
- recency blend
- conservative Edge Score
- Shadow Allocation Multiplier

## Shadow allocation range
- minimum: 0.50x
- maximum: 1.25x

Groups below the maturity threshold remain collecting.
Negative expectancy or weak hit rate produces UNDERWEIGHT_SHADOW.
Strong evidence can produce OVERWEIGHT_SHADOW.

## Safety hierarchy
Adaptive allocation cannot override:
1. Portfolio Risk blockers
2. Data Quality degradation
3. Drift/Edge Risk warnings

If Drift Monitor reports EDGE_RISK, the shadow multiplier is capped at 0.75x.
If Data Quality is DEGRADED, it is capped at 0.60x.

## Critical guardrail
`applied_to_portfolio_risk = false`
`applied_to_final_score = false`

The Portfolio Risk UI now displays the adaptive suggested size beside the normal size, but does not use it.

## APIs
- GET `/api/adaptive/edge-table?horizon=24&min_n=20`
- POST `/api/adaptive/assess`
