# ATLAS Cloud Collector V1

Goal: run the research collector 24/7 without leaving the Mac awake.

## Important
This package does NOT enable live trading or order execution. It only collects/researches market telemetry.

## Recommended deployment path
Use Render with a persistent disk. The app should listen on the platform-provided PORT.
Before deployment, verify `collector_server.py` reads `os.environ.get("PORT", 8080)` and stores the archive under a persistent data directory.

## Files added
- render.yaml
- Dockerfile
- Procfile
- cloud_start.py
- requirements.txt

## Data safety
Keep a local backup of the existing Smart Money archive before switching collectors.
Do not run two collectors writing to the same archive unless deduplication is enabled.

## Next deployment checklist
1. Put this folder in a private GitHub repository.
2. Create a Render web service from that repository.
3. Attach a persistent disk.
4. Set the service health endpoint to `/api/smart-money/status`.
5. Confirm COLLECTOR ONLINE remotely.
6. Confirm snapshot count increases after one hour.
7. Only then stop the Mac collector.
