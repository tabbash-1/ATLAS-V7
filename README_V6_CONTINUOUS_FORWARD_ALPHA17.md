# ATLAS V6 Continuous Forward Lab + Performance Dashboard — Alpha 17

Research-only. Live execution disabled.

## Continuous Forward Lab
While the ATLAS dashboard process is active:
1. Runs the Opportunity Scanner on a schedule.
2. Enriches the top candidates with Futures / Liquidity / Pattern Memory.
3. Keeps only candidates above a configurable Final Score.
4. Requires a valid directional Trade Plan.
5. Freezes up to a configurable number of candidates per scan.
6. Uses a 50-minute symbol+direction dedup window by default.
7. Stores Playbook, Regime, Volume, Futures, Liquidity, R:R, Anomaly and score context.
8. Matures 1h / 4h / 12h / 24h forward returns later.

Defaults:
- every 60 minutes
- minimum Final Score 68
- max 3 stored candidates per scan

## Performance Dashboard
24h forward results can be broken down by:
- asset
- Long vs Short
- ATLAS score bucket
- Playbook
- Regime
- Manual vs Continuous source

Metrics:
- N
- hit rate
- average directional 24h return
- profit-factor proxy
- cumulative-return max-drawdown proxy
- total return proxy

These are research proxies, not realized account P&L.

## Important limitation
Alpha 17 automatic scanning runs while the dashboard/process is active.
A later cloud-worker deployment can make the same research cycle 24/7 without relying on an open browser/Mac.

## Guardrails
- No exchange orders.
- No leverage or capital allocation is changed.
- Automatic records are deduplicated.
- Performance grouping does not alter Final Score.
