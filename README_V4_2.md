# ATLAS V4.2 — Smart Money Timeline + Forward Returns

V4.2 preserves the V4.1 archive and adds forward-return labels for every snapshot:
1h, 4h, 12h, 24h.

It also computes simple Pearson correlations between each observed factor and future return.
These are research diagnostics only, not trading signals.

Run:
    python3 collector_server.py

Open:
    http://localhost:8080

Important: copy the `data/` folder from V4.1 into V4.2 if it is not already present so no collected snapshots are lost.
Live execution remains disabled.
