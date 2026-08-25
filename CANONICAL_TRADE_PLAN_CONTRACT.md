# ATLAS Canonical Trade Plan Contract

1. `production_decision.trade_plan` is the single source of truth for user-facing action, entry mode, entry, stop, TP1, TP2 and RR.
2. When `trade_plan.status == ACTIONABLE`, AI Council must return `PRODUCTION_NOW` as `best_counterfactual` and may not replace it with WAIT/PULLBACK/BREAKOUT advice.
3. When `trade_plan.status == CONDITIONAL`, AI may explain the conditional plan but must preserve its levels and trigger.
4. Shadow/tactical counterfactuals are comparison-only and cannot override Production.
5. UI product shell and AI panel must render the canonical plan values.
6. Production threshold remains 68; geometry minimum RR remains 1.0; live execution remains disabled.
