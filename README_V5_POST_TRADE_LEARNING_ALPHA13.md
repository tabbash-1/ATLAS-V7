# ATLAS V5 Post-Trade Learning — Alpha 13

Research-only. Live execution disabled.

## Goal
Learn which conditions repeatedly accompany failed directional setups instead of hard-coding every penalty by hand.

## What is stored now
Pattern Memory observations can persist:
- S/R and breakout/breakdown context
- Volume quality / relative volume / volume flow
- Futures: funding, OI, taker ratio, book imbalance, crowding/squeeze
- Liquidity score and estimated liquidation pressure
- Anomaly score
- Master / Final / Opportunity scores when available
- Trade-plan status, quality, R:R TP1/TP2 and first obstacle
- Market regime and relative strength when available

## Failure attribution
For matured 24h directional outcomes, ATLAS generates discrete risk tags such as:
- weak volume / low relative volume
- long near strong resistance / short near strong support
- poor breakout/breakdown quality
- futures conflict / crowded funding
- taker or order-book pressure against the trade
- adverse liquidity
- poor R:R
- weak relative strength
- crowding / squeeze risk

Each tag is compared with the global matured baseline.

## Anti-overfitting protections
- No learned penalty below 20 matured cases.
- Sample-size maturity weights.
- Empirical-Bayes-like shrinkage toward the global baseline.
- Split-half stability test.
- Promotion candidate requires >=80 cases, stability in both halves, and a meaningful penalty.
- Correlated tags are grouped by risk family so only the strongest tag per family contributes.
- At most the top 3 non-overlapping shadow penalties are combined, capped at 18 score points.

## Critical guardrail
Learned penalties are NOT applied to Final Opportunity or Master Conviction in Alpha 13.
The UI shows `would_reduce_score_by`, but `applied_to_final_score=false`.

A later version may promote only rules that survive additional forward / out-of-sample validation.

## APIs
- GET `/api/learning/failure-rules?symbol=BTCUSDT&horizon=24`
- POST `/api/learning/assess`
