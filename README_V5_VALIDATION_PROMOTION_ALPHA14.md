# ATLAS V5 Validation & Promotion — Alpha 14

Research-only. Live execution disabled.

## Goal
Prevent ATLAS from promoting learned failure rules merely because they looked good in the same data used to discover them.

## Method
- Matured directional observations are sorted chronologically.
- Early sample = Discovery.
- Later sample = Validation.
- Rules are discovered ONLY in Discovery.
- Candidate rules are judged ONLY in Validation.
- A rule must remain harmful out-of-sample and filtering it must improve later-sample expectancy.
- Max-drawdown proxy is checked so an apparent expectancy gain does not come with a materially worse drawdown profile.
- Insufficient samples are rejected/waiting automatically.

## Promotion states
- PROMOTED_SHADOW
- REJECTED_OR_WAITING

Even PROMOTED_SHADOW rules are NOT applied to Master Conviction or Final Opportunity scores in Alpha 14.

## Combined validation
ATLAS also evaluates all promoted tags together:
- baseline validation expectancy
- expectancy after filtering promoted failure conditions
- cumulative-return max drawdown proxy
- fraction of setups retained

## Synthetic safety tests
1. Persistent bad pattern across Discovery + Validation → promoted in Shadow.
2. Pattern bad only in Discovery but good in Validation → rejected automatically.

## APIs
- GET `/api/learning/validation?symbol=BTCUSDT&horizon=24`
- POST `/api/learning/promoted-assess`
