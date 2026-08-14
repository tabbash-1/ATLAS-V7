# ATLAS V6 Cloud Forward Worker — Alpha 18

Research-only. Live execution disabled.

## What changed
Alpha 17 could auto-scan only while the browser/dashboard process remained active.
Alpha 18 adds a server-side Forward Worker inside `collector_server.py`.

When deployed to a persistent cloud web service, the worker:
1. wakes on a configurable interval;
2. fetches 1h Binance spot candles for BTC / ETH / SOL / XRP / BNB / DOGE / ZEC;
3. evaluates trend, RSI, ATR, relative volume, rolling S/R room and BTC-relative strength;
4. enriches directional candidates with the existing Binance Futures collector (funding, OI, taker ratio, order-book imbalance);
5. assigns a server-side research score and Playbook label;
6. keeps only candidates above the configured threshold;
7. freezes up to N candidates through the same Champion/Challenger Forward archive;
8. deduplicates repeated symbol+direction observations;
9. updates 1h / 4h / 12h / 24h forward outcomes.

## Default cloud settings
- enabled: yes
- interval: 3600 seconds
- minimum score: 68
- max candidates per cycle: 3

Environment variables:
- `ATLAS_CLOUD_FORWARD_ENABLED`
- `ATLAS_CLOUD_FORWARD_INTERVAL_SECONDS`
- `ATLAS_CLOUD_FORWARD_MIN_SCORE`
- `ATLAS_CLOUD_FORWARD_MAX_PER_CYCLE`

## Health / controls
- GET `/api/cloud-forward/status`
- GET `/api/cloud-forward/run`
- Existing `/api/performance/dashboard` includes cloud observations via `by_source`.

## Important design note
Alpha 18's server-side scanner is a compact headless research scanner, not a byte-for-byte port of the browser Opportunity Scanner.
Both record into the same Forward Lab so their performance can be compared by source before the cloud scanner is trusted as equivalent.

## Guardrails
- No exchange orders.
- No API keys for trading.
- No capital allocation.
- Cloud scanner score cannot change the browser Final Score.
- Cloud results are explicitly tagged `CLOUD_FORWARD_ALPHA18`.
