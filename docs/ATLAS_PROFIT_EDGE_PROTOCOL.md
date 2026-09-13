# ATLAS Profit Edge Protocol

## Product objective
ATLAS is a 4–12 hour crypto trading-intelligence product. Its canonical decision is exactly one of LONG, SHORT, or WAIT. It does not promise profit and must not increase trade count merely to appear active.

## Source of truth
- Production decision source: `FINAL_TRADE_GATE`.
- Only canonical `TRADE_READY` decisions may enter the $10,000 paper portfolio.
- Entry, SL, TP1, TP2, direction, timestamp and decision ID are frozen at capture.
- Historical outcomes must never modify production thresholds or past decisions.
- Live execution remains disabled.

## Decision hierarchy
Use 1D for regime/context, 12H for major structure, 4H for setup structure, 1H for confirmation. 15m may only refine execution after the HTF thesis exists. 5m/1m are outcome-settlement/refinement data, not a reason to reverse the canonical 4–12H thesis.

## Trade-ready requirements
A canonical trade must have all of the following before `TRADE_READY`:
1. Directional HTF thesis with no unresolved critical conflict.
2. Confirmed trigger; do not chase an extended price.
3. Explicit Entry, structural invalidation/SL, TP1 and TP2.
4. Computed R:R and acceptable reward relative to risk.
5. Fresh, non-degraded required data.
6. Evidence/reason trace sufficient to explain the decision.
7. A stable decision ID suitable for immutable prospective capture.

Otherwise the canonical action is WAIT, with a machine-readable reason and a concrete condition that could change the decision where available.

## Expected-value discipline
Confidence/score alone is not evidence of profitability. Where calibrated probabilities and trading costs are actually available, report net expected value as:

`EV = P(win) * reward - P(loss) * risk - fees - slippage - funding`

If those inputs are not calibrated/available, label EV `UNAVAILABLE`; never manufacture a probability or EV from the score.

## Portfolio truth
Start equity: $10,000. Risk sizing is prospective. Report at minimum entries, closed, unresolved, wins/losses, win rate, net P&L, net R, average R, profit factor, peak equity and max drawdown. Gross results must be labeled gross until fees, slippage and funding are deducted.

## Evidence standard
Do not call ATLAS profitable from a tiny sample. Separate observed facts from claims. Performance claims require a materially larger prospective sample across market regimes; 30–50 closed forward trades is an initial evidence checkpoint, not a guarantee of future profitability.

## Change-control protocol
Any material signal/gate change requires:
1. written hypothesis;
2. regression tests;
3. out-of-sample/historical evaluation when appropriate;
4. prospective forward evaluation;
5. comparison against the prior version without rewriting history.

Never tune thresholds to make already-known outcomes look better.

## Production verification
A change is not complete until code is tested, committed, deployed, and the live production endpoint/UI is verified against the intended commit. Repository snapshots are evidence artifacts but are not, by themselves, proof of current live behavior.

## Current evidence checkpoint (2026-09-13)
The canonical paper snapshot records 3 closed prospective trades from a $10,000 start: 2 wins, 1 loss, $10,153.36 equity, +$153.36 gross paper P&L, +1.5592R, 66.67% win rate, 2.5336 profit factor, and 1.0% max drawdown. This is encouraging but statistically insufficient to establish a durable trading edge. Fees, funding and slippage are not deducted.

The same snapshot records 4H average +0.0161R, 8H +0.4017R, and 12H +0.5197R across only 3 matured observations. Keep the product horizon at 4–12H and continue prospective collection without changing the production threshold solely because of these outcomes.

## Immediate engineering priority
Keep the immutable canonical portfolio as the judge of future strategy changes, then add cost-aware net performance and calibrated probability/EV only when their inputs are real and testable. Do not replace the current gate with an unvalidated scoring formula.