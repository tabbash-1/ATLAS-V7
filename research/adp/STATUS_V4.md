# ADP Research Status — V4

Status: **NOT COMMERCIAL READY — FORWARD RESEARCH ONLY**

Production effect: NONE. ATLAS Production / FINAL_TRADE_GATE unchanged.

## Evidence

- V1 direct EMA/momentum predictor rejected: validation/test direction accuracy stayed below 50% at key horizons.
- V2 preregistered candidate scan rejected as a direct predictor: best validation 8H accuracy was 50.60%.
- V3 frozen contrarian holdout showed asymmetry:
  - BUY: 64.57% (4H), 60.00% (8H), 61.30% (12H), n=460.
  - SELL failed; it is excluded.
- V4 LONG-only independent older-year replication:
  - 4H 52.27%, 8H 56.32%, 12H 55.85%, n=2,573.
  - All 11 symbols were above 52% directional accuracy at 8H.
- Tradability falsification, fixed 8H exit, 10 bps round-trip cost, no overlapping positions per symbol:
  - n=6,198
  - win rate 50.61%
  - average net return -0.0646%
  - profit factor 0.9319
  - net return sum -400.1012 percentage points

## Decision

The V4 directional effect is interesting but does **not** survive the current simple cost-adjusted trading translation. It must not be advertised as profitable, merged into Production, or sold as a validated trading system.

The Pine file is a research visualization/alert prototype only. SELL remains disabled because it failed holdout validation.

## Next evidence required

A new entry/exit formulation must be developed without reusing the exhausted holdouts for tuning, then frozen and evaluated on new forward observations. Commercial-readiness claims require positive cost-adjusted expectancy and profit factor > 1 on forward evidence, with acceptable drawdown and stable cross-symbol behavior.
