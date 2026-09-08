# ATLAS Golden Thesis Engine

`ATLAS_GOLDEN_THESIS_ENGINE_V1_SHADOW` is a deterministic 4–12H thesis/falsification layer bound after the canonical Final Trade Gate.

## Authority

- 12H + 4H define product direction.
- 1H confirms entry timing and cannot flip product direction.
- Canonical HTF geometry is mandatory for a valid thesis.
- Final Trade Gate remains the only TRADE READY authority.
- Golden Thesis cannot change Production score, threshold, geometry, LONG/SHORT/WAIT, paper eligibility, or execution policy.

## Falsification

Every candidate explicitly records supporting evidence, opposing evidence, fatal invalidations, and the strongest countercase. A missing HTF direction, missing canonical geometry, quality block, or degraded data invalidates the thesis.

## Promotion rule

Shadow output may only acquire Production decision authority after independent chronological holdout testing and prospective forward validation at 4h/8h/12h demonstrate improvement without retrospective relabeling, threshold manipulation, or increased risk. Until then `can_override_canonical_decision=false` and `live_execution=false` are invariant.
