"""ATLAS Adaptive Evidence Engine V1.

Research/shadow only. This module does not alter Production, threshold 68,
or Final Trade Gate. Rules are frozen from the 730-day indicator attribution
study and must be validated prospectively before any promotion.
"""

VERSION = "ATLAS_ADAPTIVE_EVIDENCE_ENGINE_V1_SHADOW"
RESEARCH_ONLY = True
CAN_OVERRIDE_PRODUCTION = False
CAN_EXECUTE = False
PRODUCTION_THRESHOLD_UNCHANGED = 68


def _b(v):
    return bool(v)


def evaluate(symbol, direction, *, htf_4h, htf_12h, confirm_1h=False,
             rsi_aligned=False, structure_break=False, volume_confirmed=False):
    """Return a shadow evidence verdict without changing canonical ATLAS.

    Supported discovery candidates are deliberately narrow:
      XRPUSDT LONG: HTF alignment + 1H + RSI; structure upgrades to A+.
      ZECUSDT: HTF alignment + structure + volume; 1H is supporting evidence.
    Everything else remains WAIT/UNVALIDATED until independent evidence exists.
    """
    symbol = str(symbol).upper()
    direction = str(direction).upper()
    h4 = str(htf_4h).upper()
    h12 = str(htf_12h).upper()

    base = {
        "version": VERSION,
        "research_only": RESEARCH_ONLY,
        "can_override_production": CAN_OVERRIDE_PRODUCTION,
        "can_execute": CAN_EXECUTE,
        "production_threshold_unchanged": PRODUCTION_THRESHOLD_UNCHANGED,
        "symbol": symbol,
        "direction": direction,
        "decision": "WAIT",
        "grade": "NO_SETUP",
        "reasons": [],
    }

    if direction not in {"LONG", "SHORT"}:
        base["reasons"].append("NO_DIRECTION")
        return base
    if h4 != direction or h12 != direction:
        base["reasons"].append("HTF_4H_12H_NOT_ALIGNED")
        return base

    if symbol == "XRPUSDT" and direction == "LONG":
        if not _b(confirm_1h):
            base["reasons"].append("WAIT_FOR_1H_CONFIRMATION")
            return base
        if not _b(rsi_aligned):
            base["reasons"].append("WAIT_FOR_XRP_RSI_ALIGNMENT")
            return base
        base["decision"] = "SHADOW_CANDIDATE"
        base["grade"] = "A+" if _b(structure_break) else "A"
        base["reasons"] = ["XRP_LONG_HTF_1H_RSI_CONFIRMED"]
        if _b(structure_break):
            base["reasons"].append("4H_STRUCTURE_BREAK_CONFIRMED")
        if _b(volume_confirmed):
            base["reasons"].append("VOLUME_SUPPORTING_ONLY")
        return base

    if symbol == "ZECUSDT":
        if not _b(structure_break):
            base["reasons"].append("WAIT_FOR_4H_STRUCTURE_BREAK")
            return base
        if not _b(volume_confirmed):
            base["reasons"].append("WAIT_FOR_VOLUME_CONFIRMATION")
            return base
        base["decision"] = "SHADOW_CANDIDATE"
        base["grade"] = "A+" if _b(confirm_1h) else "A"
        base["reasons"] = ["ZEC_HTF_STRUCTURE_VOLUME_CONFIRMED"]
        if _b(confirm_1h):
            base["reasons"].append("1H_SUPPORTING_CONFIRMATION")
        # RSI is intentionally not required for ZEC based on attribution evidence.
        return base

    base["reasons"].append("ASSET_DIRECTION_MODEL_NOT_VALIDATED")
    return base
