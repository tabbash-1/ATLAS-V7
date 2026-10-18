# Edge 90-day nonoverlapping cost audit — phase 4

The 90-day 11-asset research audit found that **all four** static direction
baselines had negative hypothetical net expectancy with a 17bp roundtrip cost.
The best, 12H BTC aligned, averaged -0.01181R on the prior chronological
holdout. A market-regime subgroup appeared positive only in that holdout.

This script isolates **measurement sensitivity**. It is not a strategy,
trading signal, profitability promotion or active production change.

## What is held fixed before running
- 90 calendar days of real contiguous Binance Spot 1H candles, 11 symbols.
- Same four fixed baseline policy directions as Edge V1: 4H momentum,
  4H reversal, BTC-aligned 4H, BTC-aligned 12H.
- Same initial research stop (1.5 ATR), target (2.5R) and hypothetical
  next-open entry, following first TP/SL touch within 12h.
- To reduce within-coin outcome-window overlap, evaluate **all three
  fixed 12h clock phases** derived from the original 4h observation grid.
  Phase 0 is retained as the comparison with the prior report; phases 1 and 2
  are included explicitly as robustness tests, never chosen after outcomes.
  Separate each phase by chronological 70/30 split with 24h pre-holdout gap.
- Recompute the same frozen gross price paths under round-trip costs
  0, 5, 10, 17, 25bps. These costs are deliberately scenario-only.
- Cluster resampling by **UTC calendar day** (500 fixed-seed draws) retains
  same-day coin co-movement; these intervals are descriptive and are not
  prospective significance tests.

## Can we claim profit?
No. Previous examination of these dates means the historical holdout is
**not blind**. The fixed 12h phase is a design constraint rather than
outcome selection, but calendar regimes, serial effects, shared BTC
exposure and spot/futures fee differences remain. True venue-specific
maker/taker fees, spread, slippage, funding, and real fills are not observed.
A positive value in any cost scenario must NOT be promoted or reported as
live Production profitability.

This PR is strictly independent of Final Trade Gate, thresholds,
canonical paper portfolio, execution authorization, or Production API.

## How to reproduce
```bash
PYTHONPATH=. python3 research/edge_nonoverlap_cost_audit_v1.py \
    --days 90 --output /tmp/edge_nonoverlap_report.json
```

The CI pull request workflow produces a real-data artifact, with fixed
research hypotheses and fail-closed data-source checks.

## Next decision
If even a nonoverlapping 12h cohort has nonpositive cost-adjusted expected
R, no change to production geometry/scoring is justified. If a cohort
looks positive, it is still only an exploratory hypothesis; verify spread,
funding and fees from the intended market and collect truly new, frozen
forward data before upgrading any decision logic.
