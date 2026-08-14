# ATLAS V7 Alpha 25 — Cloud Hardening

This patch preserves research-only mode and does not enable live execution.

Changes:
- Spot market data now uses official public-market-data/fallback Binance endpoints instead of one hard dependency.
- Cloud Forward status records the failing stage and last successful cycle.
- Futures-source failure no longer fabricates a neutral futures signal; confirmed alerts require futures data.
- Confirmed alerts now fail closed when portfolio permission is unknown, data quality is not HEALTHY, or drift is not STABLE.
- Cloud R:R is derived from ATR risk and observed support/resistance; no fixed 2.2 R:R is injected.
- Data quality is DEGRADED while the forward/smart-money sample is insufficient.
- Source/config/data files and directory listings are blocked from public static serving.
- POST APIs require a same-origin browser request.
- /health reports collector health and Render healthCheckPath now points to it.
- Persistent storage remains configured through /var/data in render.yaml (Starter plan + disk).

Deployment note: the manually-created Free Render service does not inherit the Starter persistent-disk guarantees from render.yaml. For 24/7 collection, deploy from render.yaml/Blueprint or configure equivalent paid service + persistent disk.
