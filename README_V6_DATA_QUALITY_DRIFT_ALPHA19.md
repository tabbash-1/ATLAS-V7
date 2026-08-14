# ATLAS V6 Data Quality & Drift Monitor — Alpha 19

Research-only. Live execution disabled.

## Purpose
Detect when the data pipeline degrades or when a previously useful edge weakens over time.

## Data quality checks
- missing entry values
- missing directions
- duplicate 50-minute symbol+direction buckets
- stale Smart Money snapshots
- overall quality score and HEALTHY / WATCH / DEGRADED state

## Drift checks
Compares the most recent 30 matured 24h observations against the prior 60:
- average directional return
- hit rate
- cumulative-return drawdown proxy
- source performance
- playbook performance

Alerts:
- EXPECTANCY_DROPPED
- HIT_RATE_DROPPED
- DRAWDOWN_EXPANDED
- PLAYBOOK_DRIFT:<name>

If deterioration is material, ATLAS reports:
`EDGE_RISK` and `PAUSE_PROMOTION_RESEARCH`.

## Guardrail
Alpha 19 does NOT automatically stop the Cloud Worker or change Final Score.
It is an independent warning layer so the system cannot silently continue promoting rules during apparent edge decay.

## APIs
- GET `/api/data-quality`
- GET `/api/drift?horizon=24&recent=30&prior=60`
