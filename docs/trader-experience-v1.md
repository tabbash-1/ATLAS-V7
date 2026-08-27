# ATLAS Trader Experience v1

## Goal

ATLAS Trader Experience v1 turns the existing research terminal into a decision-first workflow for a trader while preserving canonical Production authority.

The trader should be able to answer, in order:

1. Is there a trade now?
2. Which asset and direction?
3. Is it qualified or still waiting for a condition?
4. What are Entry, Stop, TP1, TP2 and R:R?
5. Is the Production snapshot fresh enough to act on?
6. What position size matches the user's chosen account risk?
7. What happened after entry?
8. What can the closed outcomes teach Research without silently changing Production?

## User Flow

### 1. Decision Desk — `trader.html`

Reads canonical Production state from `status/atlas-production-latest.json`.

Shows:
- selected market and canonical LONG / SHORT / WAIT state;
- `production_score` against the Production threshold of 68;
- qualification gap or pending canonical condition;
- Entry, Stop, TP1, TP2 and R:R;
- canonical trigger / entry condition;
- opportunity ranking using actionable status first, then Production score;
- decision evidence;
- lifecycle state: WATCHING → QUALIFIED → WAITING CONDITION / ACTIONABLE;
- snapshot freshness;
- user-controlled position sizing.

### 2. Freshness Guard

Trader Desk displays the age of the Production snapshot.

- Under 20 minutes: fresh.
- 20–59 minutes: aging warning; refresh before execution.
- 60 minutes or more: stale danger; do not treat ACTIONABLE as current without a fresh snapshot.

Freshness is a user-safety display. It does not modify Production scoring.

### 3. Position Sizing

The user supplies:
- account size;
- risk percentage per trade.

ATLAS calculates:
- maximum cash loss;
- quantity and approximate notional using canonical Entry-to-Stop distance.

Position sizing is informational and user controlled. It cannot qualify a trade or change Production.

### 4. Live Trade Monitor — `trade-monitor.html`

The selected symbol is passed from Trader Desk to the monitor.

The monitor:
- preserves the canonical ATLAS plan;
- reads Binance's public ticker for live monitoring only;
- refreshes price approximately every 15 seconds;
- refreshes the Production snapshot approximately every 60 seconds;
- handles LONG and SHORT separately;
- derives PRE-ENTRY, ACTIVE, TP1 HIT, TP2 HIT or STOPPED;
- shows unrealized PnL, R multiple, distance to Stop and next target;
- accepts the actual fill and quantity for paper/manual tracking.

It never places, modifies or closes an exchange order.

## Outcome Contract — `ATLAS_TRADE_OUTCOME_V2`

A saved local outcome can include:
- close timestamp and decision timestamp;
- symbol, direction, state and monitoring mode;
- Production score, council confidence and horizon;
- canonical status, entry mode and trigger;
- Entry, Stop, TP1, TP2, exit price and quantity;
- PnL and R multiple;
- the full saved Production evidence snapshot, including factor name, value, weight, detail and source when available;
- `research_only: true`;
- `production_change_allowed: false`.

This lets Research study why a trade won or lost instead of storing only a final PnL number.

## Feedback Lab — `feedback-lab.html`

Feedback Lab reads the local outcome dataset and provides descriptive research summaries:
- closed outcomes;
- wins / losses;
- win rate;
- average and median R;
- net PnL;
- breakdown by symbol;
- breakdown by direction;
- breakdown by Production score band;
- breakdown by entry mode;
- evidence attribution comparing outcomes when a factor was positive vs negative;
- dataset import/export.

Evidence attribution is descriptive research, not proof of causality.

## Research Sample Tiers

Closed outcome counts are interpreted conservatively:

- Fewer than 10: `HYPOTHESIS` only.
- 10–19: `PRELIMINARY` evidence.
- 20 or more: `SERIOUS_CANDIDATE` for research review only.

For a positive-vs-negative evidence split, each side should have at least 5 observations before the split is treated as reviewable.

These tiers do not authorize Production changes.

## Offline Research Analyzer

`trade_feedback_analysis.py` analyzes exported feedback datasets outside the browser.

It reports:
- overall outcome statistics;
- research tier;
- symbol, direction and entry-mode groups;
- positive vs negative evidence attribution.

Its output contract explicitly keeps:
- `research_only = true`;
- `auto_promotion_enabled = false`;
- `production_threshold_changed = false`;
- `production_score_adjustment = 0`.

## Regression and Safety Workflow

`.github/workflows/trade-feedback-research.yml` validates the Trader/Feedback research layer.

It checks:
- Python syntax;
- feedback regression tests;
- the research-only safety contract;
- absence of order-placement endpoints in the Live Monitor.

## Production Authority and Safety Invariants

Trader Experience v1 must preserve all of the following:

1. Production threshold remains 68 unless a separate, explicit, validated Production change is approved.
2. Research feedback cannot silently change a Production score.
3. Feedback cannot auto-promote a rule, threshold or weight.
4. Trader pages do not place exchange orders.
5. A stale snapshot cannot be presented as equivalent to fresh execution authority.
6. Position sizing is separate from signal qualification.
7. Outcome attribution remains descriptive until independently validated.

## Known Limitations

Trader Experience v1 is intentionally conservative.

- The journal currently uses browser `localStorage`; it is not a centralized server-side trade database.
- Multi-device history requires dataset export/import.
- Live monitoring depends on access to Binance's public ticker and network/CORS availability.
- Polling the current price does not reconstruct exact intrabar sequencing if both a target and stop were touched between polls.
- Manual and paper monitoring are supported; authenticated exchange order management is not part of v1.
- Feedback records can still be correlated; future research should de-correlate repeated/related trade episodes before treating them as independent evidence.
- Evidence attribution can be regime-dependent and should not be treated as causal without out-of-sample validation.
- The original `index.html` remains the full Research Terminal; Trader Desk is the decision-first surface.

## Definition of Done — v1

Trader Experience v1 is functionally complete when the following exist and remain safe:

- decision-first Trader Desk;
- correct canonical Production status mapping;
- Production-score ranking;
- snapshot freshness guard;
- user-controlled position sizing;
- selected-symbol Live Trade Monitor;
- LONG/SHORT-aware lifecycle and PnL/R tracking;
- outcome journal with decision evidence snapshot;
- Feedback Lab with import/export and attribution;
- standalone Python feedback analyzer;
- regression tests and research safety workflow;
- no automatic execution and no automatic Production promotion.

## Next Phase

The next phase is validation, not indicator expansion.

Collect real/paper closed outcomes, continue independent episode validation, and use the resulting sample to identify stable edges and failure modes. Any future Production change should be a separate proposal with out-of-sample evidence and explicit safety review.
