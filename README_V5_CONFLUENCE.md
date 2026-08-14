# ATLAS V5 Confluence Alpha — S/R + Volume

This module extends the existing ATLAS stack without replacing V4.1/V4.2, Spot Alpha, Portfolio Walk-Forward, or Smart Money Validation.

## Added
- Dynamic support/resistance zones from clustered swing pivots.
- Zone Strength Score (0–100): touches, recency, local volume, rejection wicks, role-flip bonus.
- Distance-to-wall calculation for nearest support and resistance.
- Volume Intelligence: relative volume, volume z-score, short/medium volume trend, OBV-based flow/divergence.
- Breakout / breakdown quality score.
- Trade gate: a BUY/SELL can be downgraded to WAIT when a strong opposing wall is too close and volume does not confirm a break.

## Safety / research rule
This is research-only alpha logic. It does not enable live execution and must be evaluated with forward returns and walk-forward testing before any weight is promoted into an ATLAS Master/Conviction Score.

## Next research steps
1. Persist V5 feature snapshots alongside Smart Money snapshots.
2. Label 15m/1h/4h/24h forward returns.
3. Measure rejection/breakout frequency by S/R strength bucket and volume regime.
4. Add Futures OI/Funding/Liquidation alignment to the same event rows.
5. Promote only features with stable out-of-sample improvement after costs.

## V5 Alpha 2 — Pattern Memory + Futures Intelligence

- Added server-side confluence research archive (`confluence_memory.jsonl`).
- Stores V5 S/R + volume setup features with deduplication.
- Adds 1h/4h/12h/24h forward-return labels from later observations.
- Adds setup-level hit rate and average directional return statistics.
- Adds nearest historical pattern matching using normalized feature distance.
- Adds Futures Intelligence for BTC/ETH from existing Smart Money collector: funding, OI change, taker ratio and order-book imbalance.
- Stores futures confirmation/conflict fields alongside confluence observations.
- Still research-only; no live execution and no capital weighting until out-of-sample validation.
