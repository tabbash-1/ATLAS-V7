# ATLAS staged architecture — Batch 3 shadow API scope

This batch exposes one research-only staged decision diagnostic endpoint through the existing research bootstrap.

Safety boundaries:
- FINAL_TRADE_GATE remains the sole Production decision authority.
- The endpoint reads the already-final Production decision and never wraps or replaces `production_decision`.
- Missing Regime/Flow/Cost/Risk evidence is reported as missing; it is never fabricated.
- Threshold remains 68 and the product horizon remains 4-12H with 4H/8H/12H evaluation.
- Only the seven canonical assets are accepted; HYPE is excluded from canonical scope.
- `cloud_start.py` is intentionally unchanged by this batch.
- No live execution or real-money routing is introduced.
