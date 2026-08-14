# ATLAS V7 — Alpha 25 Cloud Release Candidate 1

This is the consolidated release based on ATLAS V7 Confirmed Alerts Alpha 25.
It preserves the V7 institutional interface, Light/Dark mode, and all research layers through Alpha 25.

## Included development chain
- V5 Confluence / Master Conviction / Liquidity / Opportunity / Final Opportunity
- Event Shadow / Auto Event / Event Surprise
- Trade Management / Portfolio Risk / Anomaly
- Post-Trade Learning / Validation & Promotion / Champion vs Challenger
- V6 Playbooks / Continuous Forward / Cloud Forward
- Data Quality & Drift / Adaptive Edge / Adaptive Forward
- Promotion Gate / Controlled Canary / Stage Expansion
- V7 Institutional UI / Light-Dark Theme
- Alpha 25 Confirmed Opportunity Alerts

## Cloud hardening in this RC
- Spot market-data fallback across Binance public market-data/base endpoints.
- Forward-return maturation uses the same Spot fallback path.
- Market-data provider diagnostics for Spot and Futures.
- Smart-Money collector runtime diagnostics.
- Correct separation between Champion/Challenger forward archive and Smart-Money forward rows.
- Fail-closed Confirmed Alerts: missing Futures, portfolio approval, quality, or stable drift does not pass.
- Cloud synthetic R:R removed in the prior hardening pass; R:R is derived from ATR and observed structure.
- Static file exposure restricted; Python/YAML/README/data paths are not served.
- Directory listing disabled.
- State-changing Cloud Run and Canary Apply routes changed to same-origin POST.
- Security response headers added.
- `/health` is a lightweight liveness check for Render.
- `/api/system/readiness` exposes actual research/data readiness separately.
- Persistent Render Blueprint remains Starter + 1GB `/var/data` disk.
- Live execution remains disabled.

## Important deployment note
For true continuous collection, deploy using the settings in `render.yaml` (Starter + persistent disk).
A free Render web service may sleep and does not provide the persistent-disk configuration represented by this Blueprint.

## Current Futures limitation
Binance USDⓈ-M REST officially documents `https://fapi.binance.com` as its REST base endpoint.
If a cloud provider/location receives HTTP 451 from that endpoint, ATLAS now degrades safely:
- Spot Cloud Forward research can continue where Spot endpoints are reachable.
- Futures/Smart-Money data is marked unavailable rather than fabricated.
- Confirmed Alert gating will not pass on missing Futures evidence.
This is intentionally conservative.

## Release identity
`ATLAS_RELEASE=V7-ALPHA25-CLOUD-RC1`

Research only. Live execution disabled.
