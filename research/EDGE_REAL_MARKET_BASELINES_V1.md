# Edge real-market baseline V1 — phase 2

## What changes
Phase 1 supplied an offline all-market, paired LONG/SHORT next-open
first-touch event labeler. Phase 2 fetches **real** completed hourly Binance
spot OHLCV candles for BTC and a bounded set of 11 supported spot assets,
validates contiguous timeline coverage, and runs four predeclared simple
policy baselines on paired market-time observations.

- MOMENTUM_4H: direction of the already-completed 4h price move.
- REVERSAL_4H: opposite of the completed 4h price move.
- BTC_ALIGNED_4H: follow 4h asset momentum only if BTC 4h has same sign.
- HTF_ALIGNED_12H: follow 12h asset momentum only if BTC 12h agrees.

The 12h outcome is first-hit TP/SL or 12h expiry using frozen research
geometry **1.5 ATR stop, 2.5R target** and hypothetical next-hour open
fills. These are **not** production execution settings, and comparing
them does not amount to selecting a winner.

The historical benchmark uses one fixed chronological discovery/holdout split,
with a 12h outcome-length separation and an additional 12h purge embargo.
A strict split does *not* make overlapping 4h-spaced observations independent,
and multiple correlated assets share BTC shocks. Summary R's are descriptive
only. No model is fit, retrained, calibrated, promoted or authorized to trade.

### Run

    PYTHONPATH=. python3 research/edge_real_market_baselines_v1.py \
       --symbols BTCUSDT,ETHUSDT,SOLUSDT \
       --days 30 --modeled-cost-bps 17 \
       --output /tmp/atlas-edge-baselines.json

This requires live public HTTP market data at time of execution; no API keys,
trading account, derivatives, order routing, or automated execution.
The example 17bp cost is **unverified and illustrative**, so do not infer
cost-adjusted profitability from it. Binance spot data may not describe
perpetual futures execution/fees/funding or HYPE market data.

CI runs actual public market-data smoke verification and saves an Actions
artifact; evidence is not silently substituted with synthetic test fixtures.
Provider failures or missing candles make the job fail explicitly.

### Completion criteria
- 100% 1h contiguous calendar coverage for each downloaded symbol.
- BTC and asset candle times aligned at the same completed-hour cutoff.
- All selected observations have a frozen timestamp and only future
  settlements may consume later candles.
- Non-executable gap or ambiguous intrabar outcomes cannot count as wins.
- Direction rules and split are fixed prior to inspecting real-market holdout.
- No change to Production score, Final Trade Gate, canonical paper portfolio,
  deployment entrypoint, live execution or portfolio P&L.

### Not achieved by this PR
An economic edge, any high-accuracy prediction model, independently verified
exchange costs, selection of an optimal strategy, or evidence of forward
profitability. A successful 30-day baseline run does not prove any of these.

Next substantive study: collect longer non-overlapping representative market
periods, calibrate candidate probabilities on a fixed training window,
evaluate one untouched holdout followed by genuinely prospective shadow
data, and enforce negative controls, cluster-aware confidence intervals,
calibration error and after-cost expected R.
