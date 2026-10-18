# ATLAS — verified 90-day nonoverlapping cost sensitivity (18 Oct 2026)

## Ground truth and reproducibility

- GitHub Action: https://github.com/tabbash-1/ATLAS-V7/actions/runs/39082351858
- Real-market JSON artifact: https://github.com/tabbash-1/ATLAS-V7/actions/runs/39082351858/artifacts/12119766042
- 11 Binance Spot USDT pairs, exactly 90 days of full contiguous 1H candles each.
- Same *four frozen nonoptimized* baseline policies; research-only
  1.5ATR stop, 2.5R target, hypothetical next-1H-open fill.
- One fixed common 12h event phase: **177 timestamps instead of 530 4h
  timestamps**. Each symbol's 12h outcome windows no longer overlap.
  Assets still share BTC risk; cluster CI resamples calendar days.
- Historical 70/30 split with a 24h purge; past holdout has already been
  inspected in previous research, so it is **not blinded or prospective**.
- Roundtrip execution cost **scenarios** of 0/5/10/17/25 bps, not actual
  user-account maker/taker, bid-ask, slippage or funding.

## Results: chronological holdout, nonoverlapping events

| Policy | Valid observations | 0bp gross mean R | 5bp net R | 10bp net R | 17bp net R | 25bp net R | Break-even roundtrip bp |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4H Momentum | 577 | -0.08101 | -0.12504 | -0.16907 | **-0.23071** | -0.30115 | -9.2 |
| 4H Reversal | 577 | +0.13199 | +0.08796 | +0.04393 | **-0.01770** | -0.08814 | 14.99 |
| 4H BTC-aligned | 463 | -0.10252 | -0.14766 | -0.19280 | **-0.25600** | -0.32823 | -11.355 |
| 12H BTC-aligned | 480 | -0.11649 | -0.16069 | -0.20489 | **-0.26676** | -0.33748 | -13.178 |

Negative break-even means the gross strategy loses even at **zero**
fees, so it does not have a possible nonnegative real execution cost
that rescues these mean results. 4H reversal's 14.99bp break-even is a
*retrospective hypothetical* point estimate, not an actual feasible
execution quote or positive signal.

## Discovery period (same phase, separated before split)

| Policy | N | Mean gross R | Mean at 17bp |
|---|---:|---:|---:|
| 4H Momentum | 1,326 | +0.03247 | **-0.14853** |
| 4H Reversal | 1,324 | +0.04010 | **-0.14087** |
| 4H BTC-aligned | 1,028 | -0.00161 | **-0.18747** |
| 12H BTC-aligned | 1,024 | +0.15296 | **-0.02907** |

No baseline has positive 17bp mean in **both** periods.

## Bootstrap uncertainty for 17bp retrospective holdout mean

500 seeded resamples clustered by calendar day (includes all assets in
the sampled day); a descriptive interval only, **not** a prospective
statistical significance claim:

- 4H Momentum: **[-0.41245, -0.04380] R**
- 4H Reversal: **[-0.18293, +0.13470] R**
- BTC-aligned 4H: **[-0.48590, -0.02679] R**
- BTC-aligned 12H: **[-0.50444, -0.01892] R**

Reversal interval crosses zero; a positive future expected return is
not established. Common BTC shocks and regime changes remain.

## Decision and reasoning

**NO EDGE / NO PRODUCTION PROMOTION.** The previous 4h-overlapping
holdout made 12H BTC alignment appear near break-even (-0.01181R
after a modeled 17bp). On a fixed 12h nonoverlap grid it instead
falls to **-0.26676R**. This is a severe sample-design sensitivity,
not a dependable generalization. Meanwhile reversal improves but
is negative at the unchanged modeled cost and negative in discovery.

No hourly outcome was ambiguous/unexecutable for selected decisions in
the tested holdout (each strategy excluded 0 for these reasons).
Consequently moving to 5m **solely** to resolve same-hour TP/SL
order is unlikely to overturn these exact 1h-ledger results; for all
settled paths, the barrier order is already determined at hourly scale.
More granular order flow or spread would still be needed for *execution
quality*, not for relabeling this already unambiguous first-hit set.

The next credible path is frozen forward observations (not yet produced),
plus **venue-specific fee tiers, spread and order book snapshots** for
the intended execution market. Neither is provided by this historical
spot-candle audit. All measurements are hypothetical, not wallet P&L.

Production scoring, Final Trade Gate, current paper portfolio and
execution remain unchanged. The entire audit is research-only.
