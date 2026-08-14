# ATLAS Smart Money Validation V1

Adds a formal research gate on top of the Spot Portfolio / Walk-Forward lab.

- Labels each snapshot with 1h / 4h / 12h / 24h forward returns.
- Computes factor correlation and directional hit rate by horizon.
- Readiness levels: NOT_READY (<30 matured 24h), EARLY_RESEARCH (30-99), VALIDATION_READY (100-199), ROBUSTNESS_TEST_READY (200+).
- Smart Money remains excluded from live execution.
- No live execution is enabled.

Preserve archive first: python3 migrate_archive.py
Run: python3 collector_server.py
Open: http://localhost:8080
