# ATLAS BUILD LAW — V1

This contract defines when ATLAS work is allowed to be called DONE.

1. ROOT CAUSE FIRST — repair the producing defect, never mask it with thresholds, fixtures, or UI wording.
2. NO METRIC GAMING — score, confidence, RR, HTF, eligibility, and risk rules may not be weakened merely to improve trade count or historical results.
3. ONE CANONICAL AUTHORITY — FINAL_TRADE_GATE is the Production decision authority. Research/shadow lanes cannot override it.
4. RISK CONTRACT — canonical stops must be structural or use the approved ATR floor; reward/risk must be recomputed from the frozen geometry.
5. COST TRUTH — execution fees/spread/slippage are never invented. Validated cost evidence may only make eligibility stricter; claims of net RR require validated costs.
6. EVIDENCE CONTRACT — TRADE_READY requires the configured independent confirmations and current closed-candle HTF evidence.
7. REGRESSION BEFORE RELEASE — every behavior change needs regression coverage. Static version assertions must track current public contracts.
8. FULL RELEASE LOOP — change -> regression -> CI -> Production Reliability -> canonical plan -> Render deploy -> live API/UI smoke -> snapshot/settlement/paper integrity.
9. FAIL CLOSED — missing, stale, conflicting, or degraded authority evidence resolves to WAIT, never to an invented trade.
10. DONE MEANS GREEN — ATLAS is not DONE while any required current workflow is failing, Render is not on the intended main commit, canonical endpoints violate contract, or settlement/paper integrity is unresolved.
11. ANALYSIS ONLY — no live order routing, no real-money execution, and no research component may enable either.
12. CONTINUOUS REPAIR — discovering a new failure during verification returns the same change set to root-cause repair; a successful intermediate step is not completion.

This law is governance. It does not authorize relaxing trading rules or changing Production thresholds.
