# ATLAS Spot Portfolio + Walk-Forward Lab V1

Adds a long-only/cash portfolio simulator across:
BTC, ETH, SOL, XRP, BNB, DOGE, ZEC.

Research safeguards:
- Uses only information available before each rebalance.
- Executes allocation at the next daily open.
- Includes configurable round-trip friction.
- Allows cash when no asset clears the alpha-score threshold.
- Compares against BTC Buy & Hold.
- Reports return, CAGR, max drawdown, annualized daily Sharpe, fees, turnover, cash exposure and alpha vs BTC.
- No live execution.
- No parameter optimization in this version.

Preserve archive:
    python3 migrate_archive.py

Run collector/server:
    python3 collector_server.py

Open:
    http://localhost:8080
