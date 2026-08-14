# ATLAS V5 Event Intelligence — Alpha 7 Shadow

Research-only. Live execution disabled.

## What Alpha 7 adds
- Event classification for macro, regulation, ETF, exchange/security, token unlocks, listings, upgrades, whale transfers and geopolitical events.
- Impact Score and directional sentiment as research labels.
- Source tier and confirmation status stored separately.
- Event Memory archive (`data/event_memory.jsonl`).
- Forward returns at 1h / 4h / 12h / 24h using collector snapshots.
- Event-type statistics including positive/negative rate, average return and average absolute move.
- Event Radar UI for recording and reviewing shadow events.

## Critical guardrail
Events DO NOT change the Final Opportunity Score in Alpha 7.
They remain a shadow feature until enough forward outcomes exist to test whether event context improves expectancy out-of-sample.

## API
- POST `/api/events/observe`
- GET `/api/events/latest?symbol=BTCUSDT`
- GET `/api/events/timeline?symbol=BTCUSDT`
- GET `/api/events/stats?symbol=BTCUSDT`

## Next step
Add trusted live-source adapters and deduplication, then measure:
- event impact vs realized volatility
- event direction vs price confirmation/rejection
- volume/OI reaction
- performance by event class
- whether news improves the existing Final Opportunity Ranking after costs
