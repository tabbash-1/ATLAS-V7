"""ATLAS structure-aware Swing Target Engine.

Adds a separate 12-24H target lane without changing the existing quick-trade
Production geometry. The engine only promotes a swing plan when the market has
enough projected room in both percent terms and R multiples.
"""

VERSION = 'SWING_TARGET_ENGINE_V1'
MIN_SWING_MOVE_PCT = 1.5
MIN_SWING_R = 2.5


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rr(entry, stop, target):
    if None in (entry, stop, target):
        return None
    risk = abs(entry - stop)
    return abs(target - entry) / risk if risk > 0 else None


def _ahead(direction, entry, level):
    if level is None:
        return False
    return level > entry if direction == 'LONG' else level < entry


def build(*, direction, entry, stop, atr, structural_geometry=None,
          continuation_strong=False, breakout_confirmed=False):
    direction = str(direction or '').upper()
    entry = _num(entry)
    stop = _num(stop)
    atr = _num(atr)
    geom = structural_geometry or {}
    br = geom.get('breakout') or {}

    if direction not in ('LONG', 'SHORT') or None in (entry, stop, atr) or atr <= 0:
        return {'version': VERSION, 'status': 'UNAVAILABLE', 'reason': 'INVALID_GEOMETRY', 'research_only': True}

    s = 1 if direction == 'LONG' else -1
    risk = abs(entry - stop)
    if risk <= 0:
        return {'version': VERSION, 'status': 'UNAVAILABLE', 'reason': 'ZERO_RISK', 'research_only': True}

    obstacle = _num(geom.get('obstacle_price'))
    high24 = _num(br.get('prior_24h_high'))
    low24 = _num(br.get('prior_24h_low'))

    structural_levels = []
    for level, source in ((obstacle, 'STRUCTURAL_OBSTACLE'),
                          (high24 if direction == 'LONG' else low24, 'PRIOR_24H_BOUNDARY')):
        if _ahead(direction, entry, level):
            structural_levels.append((level, source))

    # TP1 protects the trade, while TP2/TP3 are deliberately reserved for a
    # larger move. Existing Production tp1/tp2 remain untouched outside this lane.
    tp1 = entry + s * risk * 1.25

    structural_far = None
    structural_source = None
    if structural_levels:
        structural_far, structural_source = max(
            structural_levels,
            key=lambda x: abs(x[0] - entry)
        )

    base_tp2_r = 2.75 if (continuation_strong or breakout_confirmed) else 2.5
    base_tp3_r = 4.5 if (continuation_strong and breakout_confirmed) else 3.5
    tp2_by_r = entry + s * risk * base_tp2_r
    tp3_by_r = entry + s * risk * base_tp3_r

    # A valid far structural level may extend TP2, but never shrink it below
    # the minimum swing geometry.
    if structural_far is not None and abs(structural_far - entry) > abs(tp2_by_r - entry):
        tp2 = structural_far
        tp2_source = structural_source
    else:
        tp2 = tp2_by_r
        tp2_source = 'MIN_SWING_R'

    # Runner adapts to ATR as a volatility floor, but is never less than the
    # R-based swing extension.
    atr_runner_mult = 5.0 if (continuation_strong or breakout_confirmed) else 4.0
    tp3_by_atr = entry + s * atr * atr_runner_mult
    tp3 = tp3_by_atr if abs(tp3_by_atr - entry) > abs(tp3_by_r - entry) else tp3_by_r

    move_pct = abs(tp2 - entry) / abs(entry) * 100 if entry else None
    rr_tp1 = _rr(entry, stop, tp1)
    rr_tp2 = _rr(entry, stop, tp2)
    rr_tp3 = _rr(entry, stop, tp3)

    enough_room = bool(
        move_pct is not None and move_pct >= MIN_SWING_MOVE_PCT and
        rr_tp2 is not None and rr_tp2 >= MIN_SWING_R
    )

    return {
        'version': VERSION,
        'status': 'SWING_READY' if enough_room else 'QUICK_ONLY',
        'reason': 'SUFFICIENT_SWING_ROOM' if enough_room else 'INSUFFICIENT_SWING_ROOM',
        'direction': direction,
        'horizon': '12-24H',
        'entry': round(entry, 10),
        'stop_loss': round(stop, 10),
        'tp1': round(tp1, 10),
        'tp2': round(tp2, 10),
        'tp3_runner': round(tp3, 10),
        'rr_tp1': round(rr_tp1, 3),
        'rr_tp2': round(rr_tp2, 3),
        'rr_tp3': round(rr_tp3, 3),
        'projected_tp2_move_pct': round(move_pct, 3) if move_pct is not None else None,
        'tp2_source': tp2_source,
        'minimum_swing_move_pct': MIN_SWING_MOVE_PCT,
        'minimum_swing_rr': MIN_SWING_R,
        'continuation_strong': bool(continuation_strong),
        'breakout_confirmed': bool(breakout_confirmed),
        'research_only': True,
        'can_override_production': False,
    }
