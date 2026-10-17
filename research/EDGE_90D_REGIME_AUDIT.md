# Edge 90-day real-market regime audit — preregistered research

**Status:** research only, not a Production trading strategy.

## Purpose

The earlier 30-day BTC/ETH/SOL sample found negative modeled net R in all
four predeclared direction baselines. This follow-up increases coverage to
90 completed calendar days and the 11 ATLAS Binance-supported spot symbols,
while deliberately **not changing** direction rules, geometry, scoring or
hypothesis thresholds in response to prior negative findings.

## Fixed assumptions and comparisons

- Exactly 11 spot symbols: BTC, ETH, SOL, XRP, BNB, DOGE, ZEC, ADA, LINK,
  AVAX, LTC as USDT pairs; HYPE is **excluded** because spot source differs.
- 90 days, 1H fully closed contiguous Binance spot candles, one unified
  end-of-hour as-of timestamp. Missing/gapped candles fail closed.
- Evidence snapshots every 4 hours from *prior* closed candles; both
  hypothetical LONG and SHORT outcomes settled in first-hit 12h windows.
- Research geometry frozen as **1.5 ATR** stop and **2.5R** target, next-hour
  hypothetical open; ambiguous TP+SL order is not counted as a win.
- Exactly four prespecified non-optimized policies: MOMENTUM_4H,
  REVERSAL_4H, BTC_ALIGNED_4H and HTF_ALIGNED_12H.
- Fixed execution-cost **scenario** of 17 bps round-trip, unverified for
  exchange/venue or funding; results are hypothetical modeled net R,
  NOT actual trading profits.
- Chronological ~70% discovery / 30% holdout with 12h label maturation +
  12h additional purge before split. Correlated cross-coin and overlapping
  12h paths mean row count must not be called an independent sample size.
- All segments predeclared without outcome-dependent optimization:
  frozen BTC prior-12h UP/DOWN/FLAT, LONG vs SHORT, 1 ATR extension
  (abs of price minus prior-20h mean / ATR14), ATR14/price >= 1%, and
  per-asset cohorts. All segments are **exploratory**, not validated signals.

## Run

    PYTHONPATH=. python3 research/edge_real_market_regime_audit_v1.py \
       --days 90 --cost-bps 17 --output /tmp/atlas-edge-90d-report.json

CI fetches real public market candles on an isolated GitHub runner,
validates all 11 symbols and uploads the raw JSON report as an artifact.
The report does not update canonical ATLAS paper portfolio, Production,
Final Trade Gate, customer-facing trades, or live execution.

## What this report can and cannot show

It can show whether fixed simple trading-direction heuristics were
historically positive or negative under hypothetical entry/geometry and
cost assumptions, whether outcomes differ by past BTC direction/regime,
and if an apparent edge is confined to a small cohort.

It **cannot** prove a causal edge, validate a fitted probability model,
establish out-of-sample profitability (given previous 30d exposure and
research iteration), claim statistically independent n, or authorize
live trade readiness. No holdout winner can be automatically promoted,
and subsequent post-hoc segment filtering must be treated as a new
hypothesis requiring untouched future samples.
