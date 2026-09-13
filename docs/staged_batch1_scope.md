# ATLAS staged architecture — Batch 1 scope

This batch is intentionally non-production.

It introduces only:
- a pure staged decision evaluator,
- explicit 4-12H / 4H-8H-12H / 7-core-assets / threshold-68 constants,
- fail-closed behavior for stale or failed mandatory gates,
- unit tests proving score cannot bypass a failed gate,
- tests proving Production entrypoints do not import the new staged module.

It does not modify cloud_start.py, cloud_web_only.py, cloud_web_only_final.py, final_trade_ready_guard.py, Render deployment behavior, canonical outcomes, or the $10k Paper Portfolio.
