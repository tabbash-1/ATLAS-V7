# ATLAS V4.1 — Smart Money Archive

Run with the collector server (not `python3 -m http.server`):

```bash
python3 collector_server.py
```

Open `http://localhost:8080`.

## What is collected every hour
BTCUSDT and ETHUSDT public Binance USDⓈ-M data:
- Mark/index price and funding rate
- Open interest and change versus the prior locally archived snapshot
- Taker buy/sell ratio and volumes
- Top-20 order-book notional imbalance from a 100-level snapshot
- 24h price change and quote volume

The archive is saved locally in `data/smart_money_archive.jsonl`.

## Research safety
- No trade execution exists.
- The Smart Money Score is experimental telemetry only and is not a probability of profit.
- Whale/exchange flow is left `NOT_CONNECTED` rather than fabricated. A verified provider can be integrated later.
- Factors should enter strategy logic only after sufficient archive history and walk-forward/out-of-sample validation.
