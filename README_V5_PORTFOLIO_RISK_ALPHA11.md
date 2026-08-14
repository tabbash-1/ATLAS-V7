# ATLAS V5 Portfolio Risk — Alpha 11

Research-only. Live execution disabled.

## Added
- Correlation matrix across BTC / ETH / SOL / XRP / BNB / DOGE / ZEC.
- Direction-aware effective correlation.
- Portfolio risk budget.
- Correlated-cluster risk budget.
- Suggested per-trade risk percentage.
- Position sizing from equity, entry and stop.
- Notional cap with leverage-aware ceiling.
- Research portfolio stored locally in the browser.

## Key behavior
A strong setup does not automatically receive full size.
Risk is reduced when a new trade duplicates an existing correlated exposure.

Example:
- LONG BTC risk 1.5%
- Candidate LONG ETH with +0.91 correlation
- Base risk 1.0%
- Suggested risk is reduced to 0.45%.

The same ETH SHORT against BTC LONG is not treated as the same directional cluster.

## Guardrails
- Portfolio risk can reduce or block position size.
- Portfolio risk never increases alpha/conviction.
- No orders are sent.
- Correlation estimates are sample-dependent and must be validated across regimes/timeframes.
