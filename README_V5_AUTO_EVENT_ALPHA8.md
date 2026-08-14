# ATLAS V5 Auto Event Intelligence — Alpha 8

Research-only. Live execution disabled.

## Automatic primary sources
- Federal Reserve Monetary Policy RSS
- U.S. Bureau of Labor Statistics CPI RSS
- U.S. Bureau of Labor Statistics Employment Situation RSS
- U.S. SEC press releases filtered to crypto/digital-asset/ETF/market-structure relevance

Sources are polled every 10 minutes by default (`ATLAS_NEWS_POLL_SECONDS`).

## New pipeline
1. Fetch official RSS/Atom sources.
2. Parse title, summary, URL and published time.
3. Filter source-specific relevance where required.
4. Fingerprint each event with title + URL + publication date.
5. Deduplicate before Event Memory storage.
6. Classify event type and assign research Impact/Sentiment labels.
7. Preserve actual publication time separately from discovery time.
8. Measure 1h/4h/12h/24h forward return when collector snapshots exist.
9. Compare early price direction with expected event direction.
10. When pre/post snapshots exist, attach taker-volume, OI, funding and order-book reaction context.

## Important guardrail
News/Event data still has ZERO weight in Final Opportunity Score.
Alpha 8 is a shadow-learning layer only.

## On-demand Futures capture
BTC, ETH, SOL, XRP, BNB, DOGE and ZEC are allowed for on-demand collector snapshots.
Automatic hourly collection remains BTC + ETH to control data volume.

## APIs
- POST `/api/news/ingest`
- GET `/api/news/sources`
- POST `/api/events/observe`
- GET `/api/events/latest`
- GET `/api/events/reactions`
- GET `/api/events/timeline`
- GET `/api/events/stats`

## Deployment note
Some official sources, especially SEC, may require a descriptive HTTP User-Agent. Configure `ATLAS_HTTP_UA` in deployment when needed.

## Next validation gate
Do not promote news into Master/Final Conviction until sufficient matured events demonstrate an out-of-sample improvement in expectancy after costs.
