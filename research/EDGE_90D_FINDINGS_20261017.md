# ATLAS Edge real 90-day audit — October 17, 2026

**Conclusion: no Production-ready positive trading expectancy found.**

## Reproducible evidence

- CI run: https://github.com/tabbash-1/ATLAS-V7/actions/runs/39059075216
- Full saved JSON: https://github.com/tabbash-1/ATLAS-V7/actions/runs/39059075216/artifacts/12110368883
- 90 days of real 1H Binance spot candles for BTC, ETH, SOL, XRP, BNB,
  DOGE, ZEC, ADA, LINK, AVAX, LTC (11 pairs, 2160 contiguous hours each).
- Four frozen, non-optimized direction heuristics; 1.5 ATR hypothetical
  stop, 2.5R hypothetical target, next-open fill, first-hit within 12h,
  17bp **modeled** round-trip cost scenario. Correlated overlapping
  observations are not independent trades.

## Global chronological holdout (last ~30% of the 90-day window)

| Fixed rule | Labeled decisions | Positive modeled outcomes | Mean gross R | Mean modeled net R | Modeled PF |
|---|---:|---:|---:|---:|---:|
| 4H momentum | 1,740 | 35.29% | +0.00565 | **-0.14354** | 0.7643 |
| 4H reversal | 1,740 | 42.18% | +0.09712 | **-0.05200** | 0.9057 |
| BTC-aligned 4H | 1,339 | 35.47% | +0.03244 | **-0.11916** | 0.8031 |
| BTC-aligned 12H | 1,363 | 38.96% | +0.13846 | **-0.01181** | 0.9787 |

**All four** mean hypothetical after-cost outcomes were negative.
BTC-aligned 12H was closest to flat but did not clear the modeled
cost assumption, and cannot be promoted.

## Discovery (first ~70%, with purge around cutoff)

Mean modeled net R, same order:

- 4H momentum **-0.14450R** (3,950 rows).
- 4H reversal **-0.16980R** (3,950 rows).
- BTC-aligned 4H **-0.15954R** (3,146 rows).
- BTC-aligned 12H **-0.09930R** (3,179 rows).

The 12H hypothesis is negative in *both* partitions.

## Regime switching and misleading subgroup positivity

Under frozen 12H BTC-alignment:
- When previously completed BTC 12H return was negative, discovery
  produced **-0.1859R** (1,459 rows), but holdout **+0.2004R**
  (657 rows). This is **not** a stable positive edge. A filter added
  after observing this contrast is outcome-driven data snooping.
- BTC 12H up: discovery **-0.0259R** (1,720 rows), holdout
  **-0.2093R** (706 rows).
- Prior 20h asset-price 1ATR extension: discovery **+0.0161R**
  (1,696 rows), holdout **+0.0172R** (737 rows). This tiny
  descriptive subcohort observation is not validation: correlated
  assets, overlapping bars, unverified costs, and post-hoc review
  prevent use as an alpha signal.

## Diagnosing cost sensitivity (not a trading recommendation)

12H BTC alignment has +0.13846R gross on holdout, reduced to
-0.01181R when an assumed **17bp** round-trip cost is charged. Under
the same simple linear cost model the holdout *mean* breaks even near
**15.7bp**, whereas the discovery period needs about **7.9bp**.
Actual fees, bid-ask spread, slippage and funding are not verified.
A weak positive gross expectancy cannot be called robust net alpha.

## Decision and next technical gate

**NO POLICY PROMOTION**. Keep Final Trade Gate, scoring, confidence
thresholds, paper portfolio and execution policy untouched.

A plausible improvement must show prospective, frozen and genuinely
untouched *after verified costs* advantage on event-time-paired
observations, with clustered uncertainty and no repeated holdout
selection. Future work should prioritize event-time entry quality,
true venue execution costs and market-regime changes rather than
retrofit filters to the above numbers.

These are historical **hypothetical** first-touch prices, not
executed ATLAS trades, realized portfolio returns, or a guarantee
of future loss/profit.
