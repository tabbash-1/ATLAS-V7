# ATLAS V5 Champion vs Challenger — Alpha 15

Research-only. Live execution disabled.

## Purpose
Measure future performance of the unchanged ATLAS decision (Champion) against a shadow version (Challenger) that subtracts only Alpha 14 out-of-sample validated failure penalties.

## Frozen forward observation
At entry time ATLAS stores:
- symbol / direction / entry
- Champion score and decision
- Challenger score and decision
- exact promoted-rule tags available at that moment
- exact validated shadow penalty
- selected context for audit

The rule set is frozen. Later learning cannot rewrite an old Challenger decision.

## Forward maturation
The collector can fill 1h / 4h / 12h / 24h returns from Binance spot data after the horizon has actually elapsed.

## Comparison
At 24h:
- Champion N / hit rate / average directional return / drawdown proxy
- Challenger N / hit rate / average directional return / drawdown proxy
- performance of setups Challenger avoided
- delta expectancy and delta hit rate

A preliminary verdict requires at least 30 matured forward observations and at least 15 Challenger observations.

## Guardrail
Even `CHALLENGER_LEADING` does not alter the Champion or send orders.
Alpha 15 is a prospective experiment, not proof of profitability.

## APIs
- POST `/api/forward/observe`
- GET `/api/forward/update`
- GET `/api/forward/stats?symbol=BTCUSDT&horizon=24`
