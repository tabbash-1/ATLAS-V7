# ADP V7 Final Evidence Decision

Status: **NOT READY — FORWARD RESEARCH REQUIRED**

Production effect: NONE.

## Frozen development/validation candidate
Rule: LONG when close > EMA20 > EMA50, 4h momentum > 0, 8h momentum > 0, relative volume >= 1; evaluate 12h close; 10 bps cost.

Development: n=1,793, avg net +0.4339%, PF 1.3947.
Validation: n=932, avg net +0.1889%, PF 1.2064, 8/11 symbols positive.

This satisfied the preregistered gate and was frozen before opening the recent-year holdout.

## Untouched recent-year holdout
n=2,272, avg net +0.1318%, PF 1.1284, win rate 45.20%.
Only 4/11 symbols had positive average net return. ZEC was unusually strong (+1.6475% average, PF 2.0056), so aggregate profitability is not sufficiently cross-symbol stable.
Formal result: passed = false.

## Decision
V7 is not commercial-ready and must not be merged into ATLAS Production or represented as a validated profitable indicator. The aggregate holdout edge is interesting enough for forward shadow research, but the general cross-symbol claim is rejected.

No further tuning is allowed on this exhausted holdout. Any V8 changes require a new prospective/chronological evidence window. Pine commercialization remains blocked until a frozen model passes forward evidence after costs with cross-symbol stability.
