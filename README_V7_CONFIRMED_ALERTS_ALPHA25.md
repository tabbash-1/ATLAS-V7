# ATLAS V7 — Confirmed Opportunity Alerts Alpha 25

Research-only. Live execution disabled.

## Purpose
Alert only when ATLAS sees a highly confirmed LONG or SHORT opportunity.

## Default confirmation gate
An alert requires ALL:
- supported symbol and LONG/SHORT direction
- Final Score >= 82
- valid Trade Plan / Entry
- R:R to TP2 >= 2.0
- Volume Quality >= 58
- no strong Futures conflict
- execution decision is not NO_TRADE
- Portfolio Risk is not blocked
- Data Quality is not DEGRADED
- Drift is not EDGE_RISK

## Anti-spam
Same symbol + direction:
- 240-minute cooldown by default
- only the first confirmed alert is stored during that window

## Delivery
- in-app toast notification
- optional sound
- optional browser/OS Notification API after user permission
- Cloud Forward Worker also evaluates candidates and stores confirmed alerts

Browser notifications require a supported browser/secure context. In-app alerts and alert history continue to work without notification permission.

## Alert Center
Command workspace shows:
- total confirmed alerts
- policy thresholds
- latest alerts
- asset / direction / score / entry / R:R / playbook

## APIs
- GET `/api/alerts/status`
- POST `/api/alerts/evaluate`

## Environment variables
- `ATLAS_ALERT_MIN_SCORE=82`
- `ATLAS_ALERT_MIN_RR=2.0`
- `ATLAS_ALERT_MIN_VOLUME_QUALITY=58`
- `ATLAS_ALERT_COOLDOWN_MINUTES=240`

## Critical meaning
`CONFIRMED` means the setup passed ATLAS's current confirmation criteria.
It never means guaranteed profit.
No order is sent.
