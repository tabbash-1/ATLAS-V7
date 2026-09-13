#!/usr/bin/env python3
"""Idempotently expose opportunity readiness after FINAL_TRADE_GATE."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
FINAL = BASE / "cloud_web_only_final.py"
MARKER = "OPPORTUNITY_READINESS_FINAL_PATCH_V1"


def apply():
    text = FINAL.read_text(encoding="utf-8")
    if MARKER in text:
        return

    install_needle = (
        'FINAL_TRADE_READY_GUARD = install_final_trade_ready_guard(atlas)\n'
        'if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):\n'
        '    atlas.WEB_SAFE_MODE["final_trade_ready_guard"] = FINAL_TRADE_READY_GUARD\n'
    )
    install_replacement = install_needle + (
        '\n# OPPORTUNITY_READINESS_FINAL_PATCH_V1\n'
        'from opportunity_readiness import install as install_opportunity_readiness\n'
        'OPPORTUNITY_READINESS = install_opportunity_readiness(atlas)\n'
        'if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):\n'
        '    atlas.WEB_SAFE_MODE["opportunity_readiness"] = OPPORTUNITY_READINESS\n'
    )
    if install_needle not in text:
        raise RuntimeError("final guard install block changed; refusing readiness patch")
    text = text.replace(install_needle, install_replacement, 1)

    route_needle = '        if parsed.path == "/api/runtime/status":\n'
    route_replacement = (
        '        if parsed.path == "/api/opportunities/ranked":\n'
        '            q = urllib.parse.parse_qs(parsed.query)\n'
        '            raw = (q.get("symbols") or [""])[0]\n'
        '            symbols = [x.strip().upper() for x in raw.split(",") if x.strip()] or None\n'
        '            try:\n'
        '                return self._json(atlas.opportunity_readiness(symbols))\n'
        '            except Exception as exc:\n'
        '                return self._json({"ok":False,"error":f"{type(exc).__name__}: {exc}","version":atlas.OPPORTUNITY_READINESS_VERSION,"research_only":True,"live_execution":False},500)\n'
        + route_needle
    )
    if route_needle not in text:
        raise RuntimeError("final handler route anchor changed; refusing readiness patch")
    text = text.replace(route_needle, route_replacement, 1)
    FINAL.write_text(text, encoding="utf-8")
    print("ATLAS boot patch: deterministic Final Gate opportunity readiness endpoint enabled", flush=True)


if __name__ == "__main__":
    apply()
