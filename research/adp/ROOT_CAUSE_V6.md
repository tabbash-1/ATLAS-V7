# ADP Root-Cause Decision — V6

Status: **GENERAL SIGNAL REJECTED / REDESIGN REQUIRED**

Production effect: NONE.

## Evidence
- V4 directional BUY effect replicated, but tradability failed after costs.
- V5 tested 24 fixed TP/SL/horizon translations; every candidate had PF < 1; best PF 0.8351.
- V6 tested 45 reversal-confirmation variants with 10 bps round-trip cost.
- Eligibility required >=500 trades and positive average net return in >=7/11 symbols.
- V6 produced no eligible candidate (best = null).

## Root cause
The current V4 bias has directional classification value but no demonstrated stable cross-symbol economic edge. Entry timing tweaks alone do not repair it.

## Governance
Do not merge V4/V5/V6 into ATLAS Production, enable SELL, advertise profitability, tune the preserved recent-year holdout, or cherry-pick a symbol as a general indicator.

## Redesign
The next model must target preregistered cost-adjusted forward expectancy, not raw accuracy. It must support abstention and advance only with positive net expectancy, PF > 1, adequate sample size, and cross-symbol stability before untouched/forward testing.
