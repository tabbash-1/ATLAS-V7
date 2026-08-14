# ATLAS — SPOT ALPHA LAB V1

This version preserves V4.2 Smart Money research and adds the first Spot Alpha research scanner.

## New
- Long-only / Cash research philosophy.
- Cross-sectional scan of BTC, ETH, SOL, XRP, BNB, DOGE.
- 30D and 90D momentum.
- Trend quality and volume confirmation.
- Volatility penalty.
- Explicit estimated round-trip trading friction.
- BUY / ACCUMULATE / WAIT / EXIT-CASH research states.
- Exportable scan JSON.
- Live execution remains disabled.

The Alpha score and net-edge value are intentionally unvalidated proxies. Do not use them as probabilities.
The next research stage must use forward returns + walk-forward validation before weights are accepted.

## Preserve your Smart Money archive
After unzipping beside the older ATLAS folders:
    python3 migrate_archive.py

Then:
    python3 collector_server.py

Open:
    http://localhost:8080
