# ATLAS V4 — Multi-Factor Intelligence Engine

Research prototype. Live execution is disabled.

## What changed from V3

V3 remains the frozen baseline. V4 adds one testable layer at a time:

1. **Market Regime Engine** (backtest-enabled)
   - ADX 14
   - EMA20 / EMA50 relationship and 5-candle EMA20 slope
   - ATR% relative to its recent median
   - Regimes: TREND_UP, TREND_DOWN, RANGE, TRANSITION
   - Volatility: LOW, NORMAL, HIGH
   - Directional V2 signals are blocked in RANGE and when they oppose a detected trend.
   - Risk scalar: HIGH volatility = 0.50x, LOW = 0.75x, NORMAL = 1.00x.

2. **Derivatives Shadow Factor** (live observational layer only)
   - Binance USDⓈ-M funding rate
   - current open interest
   - taker buy/sell ratio
   - crowding and flow score

The derivatives layer is intentionally excluded from long-history V4 backtests because Binance public historical open-interest and taker-ratio endpoints expose only about the latest 30 days. ATLAS should build its own archive before using these variables in a long-history backtest.

## Run on Mac

```bash
cd /path/to/ATLAS_MULTI_ASSET_V4
python3 -m http.server 8080
```

Open: `http://localhost:8080`

If Chrome shows an older ATLAS build, press **Command + Shift + R**.

## Recommended first experiment

- BTC/USDT
- 1D
- 1000 candles
- Initial capital: 10000
- Risk/trade: 1%
- Fee/side: 0.1%
- Click **Run V4 Backtest**

ATLAS runs V3 and V4 on the exact same candle dataset, then opens a V3 ↔ V4 comparison.

Repeat without changing parameters on ETH/USDT, then 500 candles for both. Do not tune thresholds after seeing one result.

## Research warning

A backtest is not proof of future profitability. V4 should only be accepted after repeated out-of-sample / walk-forward tests and realistic trading-cost assumptions.
