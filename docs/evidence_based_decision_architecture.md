# ATLAS Evidence-Based 4–12H Decision Architecture

Batch 1 status: isolated implementation only. Production behavior is unchanged.

Pipeline: REGIME -> HTF_DIRECTION -> FLOW_CONFIRMATION -> 1H_TRIGGER -> COST_LIQUIDITY -> VOLATILITY_RISK -> FINAL_TRADE_GATE

Invariants:
- Product horizon remains 4-12H; evaluation horizons remain 4H/8H/12H.
- 12H + 4H remain primary directional authority.
- 1H is entry confirmation, not directional authority.
- 5m/15m cannot flip canonical direction.
- Threshold remains 68.
- FINAL_TRADE_GATE remains sole Production authority.
- Missing/stale mandatory evidence fails closed to WAIT.
- No automatic real-money execution.

This module is deliberately isolated from cloud_start.py, cloud_web_only.py, cloud_web_only_final.py, final_trade_ready_guard.py, paper portfolio, and official canonical outcomes until later staged validation succeeds.
