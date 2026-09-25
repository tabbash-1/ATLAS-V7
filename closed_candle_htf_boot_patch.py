#!/usr/bin/env python3
"""Boot-time hardening for ATLAS 4-12H thesis authority.

Binance kline endpoints include the currently-forming candle. Structural authority
must not flip because a 4H/12H/1D candle is still moving, so Production analyzes
closed candles only. No score, threshold, geometry, or historical outcome changes.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent
TARGET = BASE / "htf_structural_thesis.py"
MARKER = "HTF_CLOSED_CANDLE_AUTHORITY_V1"


def apply():
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("ATLAS HTF closed-candle patch: already installed", flush=True)
        return
    import_needle = "from __future__ import annotations\nimport urllib.parse\n"
    if import_needle not in text:
        raise RuntimeError("HTF import contract changed; refusing unsafe closed-candle patch")
    text = text.replace(import_needle, "from __future__ import annotations\nimport urllib.parse\nimport time\n", 1)
    version_needles = (
        'VERSION="HTF_STRUCTURAL_THESIS_V3_MARKET_INTELLIGENCE"',
        'VERSION="HTF_STRUCTURAL_THESIS_V3_1_NEUTRAL_AUTHORITY"',
        'VERSION="HTF_STRUCTURAL_THESIS_V4_MARKET_CONTEXT"',
    )
    version_needle = next((needle for needle in version_needles if needle in text), None)
    if version_needle is None:
        raise RuntimeError("HTF version contract changed; refusing unsafe closed-candle patch")
    text = text.replace(version_needle, 'VERSION="HTF_STRUCTURAL_THESIS_V4_2_CLOSED_CANDLE_MARKET_CONTEXT"', 1)
    fetch_needle = '    return [{"time":int(x[0]),"open":_f(x[1]),"high":_f(x[2]),"low":_f(x[3]),"close":_f(x[4]),"volume":_f(x[5])} for x in raw]'
    fetch_replacement = '    # HTF_CLOSED_CANDLE_AUTHORITY_V1\n    return [{"time":int(x[0]),"open":_f(x[1]),"high":_f(x[2]),"low":_f(x[3]),"close":_f(x[4]),"volume":_f(x[5]),"close_time":int(x[6])} for x in raw]'
    if fetch_needle not in text:
        raise RuntimeError("HTF kline mapping changed; refusing unsafe closed-candle patch")
    text = text.replace(fetch_needle, fetch_replacement, 1)
    build_needle = '''def build_live_thesis(atlas,symbol,proposed_direction=None):
    frames={};errors={}
    for tf in TIMEFRAMES:
        try:frames[tf]=atlas._spot_klines(symbol,220) if tf=="1h" else _fetch_klines(atlas,symbol,tf,220)
        except Exception as exc:frames[tf]=[];errors[tf]=f"{type(exc).__name__}: {exc}"
    t=analyze_frames(frames,proposed_direction);t["symbol"]=symbol;t["fetch_errors"]=errors;return t
'''
    build_replacement = '''def build_live_thesis(atlas,symbol,proposed_direction=None):
    frames={};errors={};frame_quality={};now_ms=int(time.time()*1000)
    for tf in TIMEFRAMES:
        try:
            raw=_fetch_klines(atlas,symbol,tf,220)
            closed=[r for r in raw if int(r.get("close_time") or 0)<=now_ms]
            frames[tf]=closed
            frame_quality[tf]={"raw_candles":len(raw),"closed_candles":len(closed),"dropped_in_progress":max(0,len(raw)-len(closed)),"last_closed_open_time":closed[-1].get("time") if closed else None,"last_closed_close_time":closed[-1].get("close_time") if closed else None}
            if len(closed)<60:errors[tf]=f"INSUFFICIENT_CLOSED_CANDLES: {len(closed)}"
        except Exception as exc:
            frames[tf]=[];errors[tf]=f"{type(exc).__name__}: {exc}";frame_quality[tf]={"raw_candles":0,"closed_candles":0,"dropped_in_progress":0}
    t=analyze_frames(frames,proposed_direction);t["symbol"]=symbol;t["fetch_errors"]=errors;t["candle_policy"]="CLOSED_CANDLES_ONLY";t["frame_data_quality"]=frame_quality;t["in_progress_candles_can_change_authority"]=False;return t
'''
    if build_needle not in text:
        raise RuntimeError("HTF live thesis contract changed; refusing unsafe closed-candle patch")
    text = text.replace(build_needle, build_replacement, 1)
    TARGET.write_text(text, encoding="utf-8")
    print("ATLAS HTF closed-candle patch: 1H/4H/12H/1D now use completed Binance candles only", flush=True)


if __name__ == "__main__":
    apply()
