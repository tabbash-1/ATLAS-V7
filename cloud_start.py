#!/usr/bin/env python3
"""ATLAS compatibility entrypoint.

Render historically used ``python3 cloud_start.py`` from a manually configured
service. Keep this path permanently safe: on Render it delegates to the minimal
web-only runtime so dashboard settings cannot accidentally boot the heavy
research process again.

The pre-change full runtime is preserved in Git history and on branch
``backup/pre-render-safe-cloud-start-20260828``.
"""
from __future__ import annotations
import os
import runpy
from pathlib import Path

BASE = Path(__file__).resolve().parent

if os.environ.get("RENDER"):
    os.environ["ATLAS_CLOUD_FORWARD_ENABLED"] = "0"
    os.environ["ATLAS_WEB_ONLY"] = "1"
    print("ATLAS cloud_start compatibility guard: RENDER -> cloud_web_only.py", flush=True)
    runpy.run_path(str(BASE / "cloud_web_only.py"), run_name="__main__")
else:
    # Local/manual invocations use the memory-safe web stack by default too.
    # Heavy research continues in scheduled GitHub workflows rather than sharing
    # memory with the interactive server.
    print("ATLAS cloud_start compatibility guard: local -> cloud_start_web.py", flush=True)
    runpy.run_path(str(BASE / "cloud_start_web.py"), run_name="__main__")
