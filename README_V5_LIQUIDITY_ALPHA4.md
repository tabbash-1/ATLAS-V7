# ATLAS V5 Liquidity + Liquidation Intelligence — Alpha 4

Adds an independent research layer for liquidity context.

## Observed vs estimated
- **Observed liquidity:** Binance USDⓈ-M order-book wall levels captured directly from `/fapi/v1/depth` and stored with each new Smart Money snapshot.
- **Estimated liquidation pressure:** derived from funding/crowding, OI expansion and squeeze context. It is explicitly labelled estimated and is **not** a true liquidation heatmap.
- A true liquidation-map provider can be connected later without changing the Master Conviction contract.

## Master Conviction correction
Alpha 4 also fixes score-weight budgeting. Dynamic weights can no longer sum above 1.00. Missing research layers stay neutral instead of inflating conviction.

## Safety
Research only. Live execution remains disabled. No capital decision should depend on estimated liquidation pressure before forward validation.
