# ATLAS Cloud Collector V1.1

Recommended deployment: Render Web Service + persistent disk.

## Why V1.1
- Reads Render's `PORT` environment variable.
- Binds to `0.0.0.0`.
- Stores archive under configurable `ATLAS_DATA_DIR`.
- Health endpoint: `/api/smart-money/status`.
- Live execution remains disabled.

## Render settings
Build command:
    pip install -r requirements.txt

Start command:
    python3 collector_server.py

Environment:
    ATLAS_DATA_DIR=/var/data

Persistent disk:
    Mount path: /var/data
    Size: 1 GB

Health check:
    /api/smart-money/status

## Safety
Do not stop the Mac collector until:
1. Cloud deploy is successful.
2. Cloud status endpoint returns ONLINE.
3. Snapshot count increases after at least one scheduled interval.
4. Existing archive is backed up or migrated.

Note: Render persistent disks are available on paid services. Free web services are suitable only for deployment testing, not reliable 24/7 archive persistence.
