# Edge 180-day 1D alignment audit (research only)

## Purpose

Determine whether the daily trend context now exposed by the RC10.1
on-demand deep-analysis website actually distinguishes better 4–12H
hypothetical trade outcomes, rather than applying an untested daily veto.

**Preregistered**: before observing this new 180-day comparison we keep:
- exactly the four earlier Edge V1 fixed policies (MOMENTUM_4H,
  REVERSAL_4H, BTC_ALIGNED_4H, HTF_ALIGNED_12H)
- 11 already-supported public **Binance SPOT** USDT market series, including BTC
- exactly 180 days of continuous closed 1H candles, aligned BTC-first
- same 1.5 ATR stop and 2.5R target, first-hit outcome within 12 hours
- same **unverified scenario 17bps** round-trip costs, theoretical next-1H-open
- exactly three disjoint 12h phases selected by a fixed clock convention,
  each with chronological 70/30 discovery/holdout and a 24h purge
- same RC10.1 site's **daily bias**, calculated on only fully completed
  24-hour UTC periods, using two of three: close vs EMA20, EMA20 vs EMA50,
  RSI14 >= or <= 50.
- compare one fixed policy's prospective candidate direction against daily
  state: DAILY_ALIGNED vs DAILY_COUNTER vs DAILY_NEUTRAL.
- report every phase, both partitions and all policies. Do NOT select a
  policy, phase, cost or time period after inspecting actual outcomes.

## Key temporal invariants

Closed daily bars are **built from the same exact 1H data** used for each
frozen Edge event. A UTC daily candle is valid only if **all 24** hourly
observations exist. For an event at timestamp T, only completed days
with close_time <= T are allowed; the incomplete current UTC day is
never included. At least 60 completed full days are necessary, so
earliest warmup events are excluded from the comparison, and that
exclusion is always disclosed.

No future settlement bar influences 1D bias, and LONG/SHORT use
identical frozen observation features. Risk and targets unchanged.

## Interpretations

This identifies a *historical association* between trend context and
outcome under a specific hypothetical entry/exit model. It does NOT
prove that adding a daily-based WAIT veto causes higher profitability
or that it works for current ATLAS Production entries. Previous studies
already inspected parts of the market window, so even chronological
holdout is **not independently blinded**. All 11 assets are correlated,
not 11 independent trials.

The short side is a SPOT *counterfactual*, not a directly executable
unborrowed spot sale; intended Bybit linear order book/funding/fees
and actual fills are NOT being modeled. Any subgroup with higher
historical R requires genuinely new untouched forward evidence,
not Production rule tuning or immediate confidence inflation.

## Run

    PYTHONPATH=. python3 research/edge_daily_confluence_180d_v1.py \
      --days 180 \
      --output /tmp/atlas-edge-daily-confluence.json

On PR, CI performs offline causal regression and a **real** 180-day
11-asset public Binance Spot audit and uploads the full JSON as an
Actions artifact. CI does not commit Production state or send orders.

## Decision gate

Do **not** modify Final Trade Gate, production_signal_scoring,
thresholds, trade enrollment, canonical paper portfolio or confidence
until an independent, prespecified 1D hypothesis succeeds on genuinely
untouched forward samples net of verified execution cost.
