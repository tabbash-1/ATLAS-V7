# ATLAS V5 Event Surprise — Alpha 9 Shadow

Research-only. Live execution disabled.

## Added
- Economic Surprise Engine for Actual vs Consensus vs Previous.
- Normalized surprise magnitude with configurable scale.
- CPI and rate decisions map to preliminary Risk-On / Risk-Off context.
- Jobs data is intentionally Context-Dependent rather than forced into a simple direction.
- Surprise fields are stored in Event Memory.
- `/api/events/surprise-stats` measures 1h reaction confirmation and average returns by event class.
- Event Radar manual form now accepts Actual / Consensus / Previous / Surprise Scale.

## Guardrail
Surprise data still carries ZERO weight in Final Opportunity Score.
Promotion requires sufficient matured events and an out-of-sample expectancy improvement after costs.

## Current research question
Does surprise magnitude + price/volume/futures reaction outperform headline sentiment alone?
