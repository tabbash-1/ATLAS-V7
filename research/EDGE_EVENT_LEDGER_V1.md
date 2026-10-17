# Edge Event Ledger V1 — research only

## Problem being addressed

Production's TRADE_READY-only sample does not tell us whether the directional
hypothesis fails across the market or whether the selection/entry/geometry
layer fails. The existing Alpha Core V2 and Reversal4H directional challengers
do not establish a positive forward trade edge. Merely tuning a higher
confidence cutoff against already-settled trades risks selection bias.

This is **phase 1 data infrastructure**, not a new winning model, and not
an alternative Production trade decision.

## Exact event semantics

- Input: validated contiguous completed **1H OHLCV** for an asset and BTC.
  Missing BTC context or candle gaps fail closed; caller supplies as-of time.
- Feature timestamp: the end of a completed 1H candle. Asset 1H/4H/12H
  returns, BTC 4H/12H returns, historical volume and ATR14 are computed using
  no candle later than that timestamp.
- Universe: one observation every four closed 1H candles, for **both LONG
  and SHORT**, regardless of Production's action or retrospective outcome.
- Reference price: the observation's closing price; fixed hypothetical
  stop distance **1.5 ATR** and target **2.5 gross R**. These are V1
  research-plan assumptions, **not** Production settings.
- Hypothetical fill: the next candle's open, strictly after the observation.
  Opening beyond a frozen stop or target means GAP_UNEXECUTABLE.
- Outcome window: first stop/target touch in the following 12 closed 1H
  candles. Double touches within one hour are **AMBIGUOUS_INTRABAR_ORDER**:
  neither a fabricated win nor a loss claimed with known ordering. Other
  exits are TP_FIRST, SL_FIRST, or EXPIRED_12H.
- Cost: optional round-trip bps scenario, explicitly **not** verified venue
  spread, slippage, funding, or real execution evidence.
- 4H spacing with a 12H outcome window means **overlapping dependent rows**.
  Counts are descriptive; no naive p-values/CI, model selection, or promotion.
- Explicitly forbidden: changing Production score/threshold, bypassing Final
  Trade Gate, altering canonical $10K paper enrollment, placing orders,
  or asserting forward profitability.

## How to produce a local report

Provide JSON arrays of objects with time, close_time, open, high, low, close,
volume. Prices must be positive and bars contiguous at a 1H frequency.

    python3 research/edge_event_ledger_v1.py \
      --market-json market_1h.json \
      --btc-json btc_1h.json \
      --symbol ETHUSDT \
      --as-of-ms 1792000000000 \
      --modeled-cost-bps 17 \
      --output /tmp/eth_edge_events.json

The example as-of timestamp is illustrative; choose the timestamp that
actually covers the closed input data. The module does not fetch remote
market data and does not mutate the canonical portfolio.

## Roadmap before proposing a model

1. Validate OHLCV source, symbol coverage, data gaps and true as-of semantics.
2. Run the same frozen event labeling over an adequately long historical
   universe, excluding corrupt windows and documenting exchange differences.
3. Preregister baseline rules, calendar holdout periods and purge/embargo;
   evaluate direction separately from first-hit barrier outcomes.
4. Fit and calibrate a causal-time learner on event features with **no future
   label access**; compare to simple direction baselines and Production on
   genuinely paired event times, with venue-validated costs.
5. Collect untouched forward shadow evidence. Only a distinct reviewed PR
   may propose a Production decision change, after full regression and
   deployed-path verification.

Current state: **labelling component only**; no model fitted, no validated
profitability, no trading permission.
