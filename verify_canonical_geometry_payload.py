#!/usr/bin/env python3
"""Verify that a live ATLAS decision's reported R:R matches exact displayed levels."""
import json
import math
import sys


def verify(path):
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    direction = payload.get("candidate_direction")
    entry = payload.get("entry")
    stop = payload.get("stop_loss")
    target = payload.get("take_profit")
    gate = payload.get("geometry_gate") or {}
    if direction not in ("LONG", "SHORT"):
        return
    if not all(isinstance(x, (int, float)) for x in (entry, stop, target)):
        if gate.get("reason") != "GEOMETRY_INCOMPLETE":
            raise SystemExit(f"incomplete levels without GEOMETRY_INCOMPLETE: {gate}")
        return
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        raise SystemExit("zero-risk geometry")
    computed = reward / risk
    reported = gate.get("risk_reward")
    if reported is None or not math.isclose(computed, float(reported), rel_tol=1e-5, abs_tol=1e-5):
        raise SystemExit(f"geometry RR mismatch computed={computed} reported={reported}")
    if gate.get("rr_source") != "RECOMPUTED_FROM_EXACT_ENTRY_STOP_TARGET":
        raise SystemExit(f"wrong rr_source: {gate.get('rr_source')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: verify_canonical_geometry_payload.py decision.json [decision.json ...]")
    for filename in sys.argv[1:]:
        verify(filename)
        print(f"{filename}: exact geometry RR PASS")
