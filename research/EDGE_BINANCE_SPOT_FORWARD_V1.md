# ATLAS — Binance Spot prospective bid/ask shadow V1

## Provider decision and scope

Bybit USDT-linear public API returned HTTP 403 on GitHub Actions in the
United States. Bybit documents location-based 403 restrictions. The Bybit
branch PR #406 was **not promoted or merged**. This implementation uses
only the Binance **SPOT** public endpoints on
`https://data-api.binance.vision`, previously available to ATLAS CI.

**Do not interpret this as executable Bybit futures evidence.** There is no
spot/perpetual data blending. Spot SHORT predictions are counterfactual
only and cannot be executed as ordinary unborrowed spot sales.

## Prospective evidence rather than hindsight

- An hourly scheduled check (at minute :13 UTC) attempts to read 1000 recent fully closed 1H
  BTC, ETH and SOL Binance Spot candles and a public best bid/ask quote.
- Captures only while latest closed 1H is less than 20m old.
  Scheduler delay or unavailable provider yields **no reconstructed trade**.
  A new capture for a symbol is allowed only if the previous frozen capture
  is at least **4 hours** old, even though the scheduler checks hourly.
- The Binance public bookTicker has no exchange timestamp. The ledger records
  a LOCAL_CAPTURE_CLOCK timestamp and flags absence of a true venue quote
  timestamp. Therefore its quote is observed at call time, but strict
  exchange-clock latency freshness cannot be proven.
- Immutable observations include the latest closed BTC/asset features,
  a snapshot of the bid/ask and top-level quantities, all four baseline
  policy actions (LONG/SHORT/WAIT), and frozen hypothetical
  entry (ask for LONG, bid for SHORT), 1.5ATR stop and 2.5R target.
- Hash each capture (SHA256) and never overwrite prior observations.
  Idempotent event IDs are symbol + frozen hour + policy + version.
- Mature outcomes only when a full 720 x 1m **future** candle window
  exists. No future information is used to create a signal.
- Ambiguous same-minute TP/SL is excluded from modeled R; missing minute
  candles fail closed. First partial minute following quote is omitted,
  **so outcome paths are not complete execution evidence**.
- Modeled costs are **not verified maker/taker fees**:
  11bps round-trip fee scenario and a proxy exit half-spread using the
  opening spread. No measured exit quote, account funding, slippage,
  market impact, fill probability or borrowing costs.
- The workflow commits only to two new research files:
  `status/edge-binance-spot-forward-ledger.json` and
  `status/edge-binance-spot-forward-latest.json`.
  It has no trading API calls, order placement, Final Trade Gate access,
  canonical paper enrollment or Production scoring change.

## Operation

```bash
PYTHONPATH=. python3 research/edge_binance_spot_forward_v1.py \
  --ledger status/edge-binance-spot-forward-ledger.json \
  --latest status/edge-binance-spot-forward-latest.json
```

The workflow checks hourly at :13 UTC, captures at most every four hours per symbol and allows explicit manual dispatch.
Pull requests only test offline cases and read-only public market endpoints.
The scheduled capture can legitimately produce zero new observations when
the runner is late. Existing prospective Alpha V2 and Reversal4H research
streams continue unaffected.

## Expected evaluation

There is **no forward profitability or increased accuracy evidence** until
new observations mature, adequate independent sample size is reached,
and the exchange-specific cost and incomplete initial-minute
limitations have been addressed. Positive aggregate modeled outcomes do
not authorize strategy promotion or changing thresholds.
