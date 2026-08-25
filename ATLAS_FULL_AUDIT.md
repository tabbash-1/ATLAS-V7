# ATLAS Full Production Audit

Date: 2026-08-25
Scope: verify requested trading capabilities against code that can affect the current Production decision path. Presence of a filename or UI panel is not counted as Production integration.

## Executive finding

ATLAS contains many research and UI modules, but the current Production scoring path is materially narrower than the product concept. The most important confirmed gap is that Smart Money / Whale intelligence does not currently influence Production scoring, and the existing V4.2 Smart Money UI is not a ten-whale entity consensus system.

## Capability matrix

| Capability | Exists | Production influence verified | Audit status | Action |
|---|---:|---:|---|---|
| Trend / EMA / RSI / momentum | Yes | Yes | VERIFIED | Keep and validate outcomes |
| Paced relative volume | Yes | Yes | VERIFIED | Keep and validate outcomes |
| Relative strength vs BTC | Yes | Yes | VERIFIED | Keep and validate outcomes |
| Futures evidence | Yes | Yes when provider validated | VERIFIED WITH PROVIDER GATE | Continue provider validation |
| Prior structure / obstacle geometry | Yes | Yes | VERIFIED | Continue geometry/outcome audit |
| Continuation / breakout logic | Yes | Yes | VERIFIED | Continue forward validation |
| Canonical trade plan / geometry gate | Yes | Yes | VERIFIED | Preserve contract |
| Outcome ledger / path settlement | Yes | Yes for evaluation | VERIFIED BUT HISTORICAL COHORTS MIXED | Version all new geometry cohorts |
| Smart Money snapshots | Yes | No direct Production score influence verified | RESEARCH ONLY | Keep separate until validated |
| Ten-whale comparison | No complete implementation before this audit | No | MISSING | Build strict Whale-10 research layer, source registry, collector, forward validation |
| News / event ingestion | Yes | No direct Production score influence verified in current scorer | RESEARCH / SHADOW | Validate before any promotion |
| Liquidity / liquidation engine | Module exists | Not verified in current Production scorer | NOT IN CURRENT SCORE FORMULA | Audit data path before promotion |
| Portfolio risk | Module exists | Not verified in current Production scorer | NOT IN CURRENT SCORE FORMULA | Audit execution path |
| Pattern memory / learning | UI/research modules exist | Not verified in current Production scorer | RESEARCH | Require forward evidence |
| Multi-timeframe analysis | AI/research layer exists | Not verified as a direct current Production scoring component | PARTIAL / SEPARATE LANE | Audit alignment with canonical decision |

## Current Production score formula verified

The current `production_signal_scoring.py` formula is:

`trend_base + paced_volume_bonus + relative_strength_adjustment + futures_adjustment + prior_structure_obstacle_adjustment`

Therefore Smart Money, Whale-10, news/event intelligence, liquidity score, portfolio risk, and pattern memory must not be described as Production scoring inputs unless and until their actual code path is promoted and tested.

## Smart Money / Whale-10 gap

The existing V4.2 Smart Money client reads aggregate market/futures-derived snapshots and forward-return factor statistics. It is not an entity registry and it does not compare ten independent whale entities. Its client-side symbol selection is BTC/ETH-oriented.

A new strict research contract is now introduced in `whale10_consensus.py`:

- exactly 10 independent validated entities are required;
- exchange, custodian, bridge, burn, and unknown treasury entities are excluded;
- holder rank alone is never directional evidence;
- the output is accumulation / distribution / mixed plus a -100..100 consensus score;
- `production_eligible` is hard-coded false;
- promotion requires forward validation.

## Non-negotiable rules from this audit

1. A UI panel or module filename does not prove Production integration.
2. No feature may be called complete without a data source, runtime path, test, freshness semantics, and outcome validation.
3. No new signal factor enters Production merely because it sounds useful.
4. Every execution-qualified observation must record scoring/decision/geometry generation IDs.
5. Whale-10 must never substitute exchange hot/cold wallets for independent whales.
6. Production threshold changes require outcome evidence, not visual dissatisfaction with WAIT frequency.

## Remediation order

1. Whale-10 validated entity registry and source adapters for all Production assets.
2. Whale-10 observation archive and freshness/coverage runtime status.
3. Whale-10 forward validation (1h/4h/12h/24h plus trade-path outcomes).
4. Version IDs in every new execution/outcome row for clean cohort comparison.
5. Verify whether liquidity, news, portfolio risk, pattern memory, and multi-timeframe lanes actually reach the canonical Production decision; downgrade labels where they do not.
6. Only after sufficient forward evidence, test Whale-10 as a shadow score adjustment against the unchanged Production champion.

## Definition of done for Whale-10

Whale-10 is not complete until each supported asset can show ten validated independent entities with source confidence, observed timestamp, freshness, per-entity state, consensus, historical archive, forward outcomes, and an explicit promotion decision. Until then it remains research-only and cannot alter execution.
