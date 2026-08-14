# ATLAS V7 — Institutional Terminal UI Redesign

Presentation-only redesign built on ATLAS V6 Stage Expansion Alpha 24.

## Preservation guarantee
No ATLAS engine, endpoint, research rule, forward archive, promotion gate, canary logic, stage expansion logic, or execution guardrail was removed.

The original interface contained 224 element IDs.
V7 retains all 224 legacy IDs and adds 10 presentation-only IDs.
There are no duplicate IDs.

## New daily Command Center
Always visible:
- Master Conviction
- Market Regime
- Trade Plan
- Portfolio Risk
- Current Playbook
- Drift status
- Cloud Forward status

The current TradingView chart and Current Setup remain the visual center.

## Workspace organization
Existing cards are moved as DOM nodes — not copied or rewritten — into:
- Command
- Market
- Trade
- Research
- Learning
- System

Because the original DOM nodes are preserved, existing event listeners and engine output IDs remain intact.

## Design direction
- institutional dark terminal
- denser data hierarchy
- less visual noise
- compact status badges
- sticky command controls
- responsive desktop/tablet/mobile layout
- research-only and no-execution messaging retained

## New files
- `v7-ui-redesign.js`
- presentation overrides appended to `styles.css`

## Safety
This update changes appearance and information hierarchy only.
Live execution remains disabled.
