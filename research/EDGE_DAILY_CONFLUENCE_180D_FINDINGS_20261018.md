# Actual 180-day 1D context test — findings (18 October 2026)

Evidence: [real spot GitHub CI run](https://github.com/tabbash-1/ATLAS-V7/actions/runs/39138774888)
and [original full JSON artifact](https://github.com/tabbash-1/ATLAS-V7/actions/runs/39138774888/artifacts/12140213677).

## Decision: Daily context is informative, but NO DAILY FILTER PROMOTION

**All 14 CI workflows passed.** The actual public Binance Spot dataset
comprised 11 assets × 180 days × 24 completed hourly candles (4,320 1H
observations per asset; 47,520 total hourly records). Our daily bias
comes from 24 completed hourly candles for each full UTC day, with at
least 60 completed daily candles needed as warmup. The resulting study
excludes **3,905 symbol-event keys** for unavailable mature 1D history,
rather than fabricating a daily bias.

Hypothetical first-hit 12h paths and 17-basis-point round-trip cost
assumption were identical across matching-vs-counterfactual daily trend
groups, and analyses ran for *all* three disjoint 12h observation
phases, chronological discovery and holdout.

### BTC-aligned 12H strategy; 17bp modelled net R

| Clock phase | Discovery ALL | Discovery with 1D | Discovery counter-1D | Holdout ALL | Holdout with 1D | Holdout counter-1D |
|---|---:|---:|---:|---:|---:|---:|
| 0 | -0.32392 | -0.36103 (n=528) | -0.29216 (n=617) | +0.03552 | +0.09772 (n=469) | -0.02642 (n=471) |
| 1 | -0.03998 | +0.05043 (n=541) | -0.13227 (n=530) | +0.13680 | +0.19038 (n=506) | +0.07627 (n=448) |
| 2 | -0.14777 | -0.12341 (n=540) | -0.17009 (n=589) | -0.01704 | -0.00827 (n=476) | -0.02591 (n=470) |

Only phase 1 of this fixed policy had positive aligned-1D results in
both discovery and holdout, and **phase 0 discovery was worse when
aligned**. The predeclared rule therefore fails robustness across
clock phases and cannot become a Production rule.

### Simple 4H momentum; 17bp modelled net R

| Phase | Discovery aligned 1D | Discovery counter 1D | Holdout aligned 1D | Holdout counter 1D |
|---|---:|---:|---:|---:|
| 0 | -0.13555 | -0.12995 | -0.02544 | -0.15876 |
| 1 | -0.04714 | -0.10705 | +0.00840 | -0.05372 |
| 2 | -0.15074 | -0.21072 | -0.13290 | -0.13561 |

Directionally, daily alignment often reduced modeled losses but did
not give robust positive expected R. The reversal-4H and
BTC-aligned-4H comparisons were also non-robust and not promotable.

### Critical caveats

- These observations **are not real ATLAS Production paper trades**;
  they are simulated first-hit hypothetical entries under frozen geometry.
- Prior 90-day research already examined overlapping calendar dates.
  A 70/30 historical holdout cannot now be called independent or blind.
- 17bps is only a scenario; future funding, true venue slippage, fee
  tiers, spreads and market-impact costs are unverified.
- A daily bias based on 2/3 EMA20/EMA50/RSI gave **no neutral cohort**
  in this sample, so no meaningful neutral daily outcome can be inferred.
- Across assets, observations are correlated, and changing the 12h
  capture clock materially changes outcomes. No independent
  confidence interval or calibrated probability is established.
- Trading short Binance spot without borrowing remains a hypothetical
  counterfactual, not a ready execution path.

**Action:** Keep 1D as an explanatory factor (trend/phase/support/
resistance and daily countertrend risk) on ATLAS deep analysis. Do NOT
add a hard WAIT veto, modify confidence thresholds, override Final Trade
Gate, or claim profitable accuracy. Any future daily-based filter must
be preregistered and prospectively measured with the **new** frozen
forward cohort, net of observed venue-specific execution costs.
