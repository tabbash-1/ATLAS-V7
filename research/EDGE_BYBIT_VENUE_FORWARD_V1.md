# Edge Bybit Venue-Aware Forward Shadow V1

## Purpose and preexisting evidence

ATLAS already has separate prospective directional evidence in Alpha Core V2,
Reversal4H and paired direction shadows. The earlier **90-day, 11-asset**
static Edge analyses found no robust after-cost edge; choosing a profitable
historical clock phase would be outcome selection.

This new **research-only** system measures something those direction-only
shadows did not: contemporaneous **public Bybit USDT perpetual**
best bid/ask at actual runtime and a forward 1-minute OHLCV barrier outcome
for an immutable hypothetical plan. No keys or trading account access.

## Strict evidence semantics

* At each run, fetch **closed 1h Bybit USDT-linear** BTC, ETH, SOL
  candles and a fresh public best bid/ask quote. Each symbol is
  compared against closed BTC 1H, 4H and 12H context.
* **No missed-slot reconstruction**: latest complete 1h candle must be
  within 20 minutes of observation and quote within 60 seconds of the
  runner's timestamp. If delayed, BTC unavailable or quote incomplete,
  fail closed and record an error, **not** a fictional trade.
* Record four previously fixed directional baselines for each symbol,
  including WAIT. Original frozen feature set and quote snapshot
  are protected by a SHA256 checksum; repeated captures for the
  same symbol/policy/decision hour never rewrite the old snapshot.
* If direction is LONG, hypothetical entry references **ask**; SHORT
  uses **bid**. Stop = 1.5 closed-1h ATR; TP=2.5R. These are research
  assumptions, NOT Production trade geometry and not actual fills.
* The later settlement fetches 720 *fully future* closed 1-minute
  Bybit linear trade-price candles and labels TP_FIRST, SL_FIRST,
  EXPIRED_12H or AMBIGUOUS_1M_ORDER. A single minute crossing
  both barriers is **ambiguous**, never an invented win. Missing bars
  fail closed and stay pending.
* The partial minute immediately after quote capture is unobservable
  using only complete-minute OHLC; the ledger therefore always flags
  it as an **incomplete execution path**. Model is NOT execution-quality.
* Modeled cost combines known opening bid/ask side, frozen **assumed**
  11bp round-trip fees and a **proxy exit half-spread** based on the
  opening quote; no actual exit quote, funding, fee tier, market depth,
  fill or slippage measurement is available. Modeled R cannot be
  presented as realized account P&L.
* Never mix venue spot and linear price paths. Capture and settlement
  use Bybit USDT-linear for all recorded instruments.
* No scoring, training, online learning, adaptive thresholds or model
  promotion from this job. It NEVER creates a Production trade or a
  canonical paper-portfolio entry.

## Workflow

GitHub workflow \`.github/workflows/edge-bybit-venue-forward.yml\` checks
the public API and regression suite on PRs, then on schedule
\`13 */4 * * *\` UTC performs runtime captures/matured settlements,
committing only two isolated research files:
\`status/edge-bybit-venue-forward-ledger.json\` and
\`status/edge-bybit-venue-forward-latest.json\`.

Schedules may be late. Such runs cannot backfill missed signals and may
correctly capture **zero** new observations. Scheduler delay must not
be mistaken for lost alpha. GitHub commit history provides additional
temporal provenance but the SHA256 field alone is not a digital signature.

## Requirements for future proof

Do not call this a robust profit model until frozen observations have
sufficient *new*, truly forward maturity, strict time-paired baseline
comparison, venue-specific fees and true spread/slippage funding at
exit, uncertainty aware of common BTC exposure and an independent
reviewed promotion proposal. To improve execution-path validity,
introduce true event-level tick-level or exchange orderbook data,
especially for the sub-minute capture interval. Research-only cohort
is not authority to bypass Final Trade Gate.
