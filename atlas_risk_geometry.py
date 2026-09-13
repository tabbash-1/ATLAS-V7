from dataclasses import dataclass


@dataclass(frozen=True)
class RiskGeometryResult:
    direction: str
    entry: float
    stop: float
    tp1: float
    tp2: float
    risk_per_unit: float
    reward_tp1: float
    reward_tp2: float
    rr_tp1: float
    rr_tp2: float
    geometry_valid: bool
    reason: str


@dataclass(frozen=True)
class PositionRiskResult:
    account_equity: float
    risk_pct: float
    risk_budget: float
    stop_distance: float
    units: float
    notional: float
    atr: float | None
    stop_distance_atr: float | None


def evaluate_risk_geometry(*, direction: str, entry: float, stop: float,
                           tp1: float, tp2: float) -> RiskGeometryResult:
    direction = str(direction).upper()
    if direction not in {'LONG', 'SHORT'}:
        raise ValueError('direction must be LONG or SHORT')
    if min(entry, stop, tp1, tp2) <= 0:
        raise ValueError('prices must be positive')

    if direction == 'LONG':
        valid = stop < entry < tp1 < tp2
        risk = entry - stop
        reward1 = tp1 - entry
        reward2 = tp2 - entry
    else:
        valid = stop > entry > tp1 > tp2
        risk = stop - entry
        reward1 = entry - tp1
        reward2 = entry - tp2

    rr1 = reward1 / risk if valid and risk > 0 else 0.0
    rr2 = reward2 / risk if valid and risk > 0 else 0.0
    return RiskGeometryResult(
        direction=direction,
        entry=float(entry), stop=float(stop), tp1=float(tp1), tp2=float(tp2),
        risk_per_unit=float(risk), reward_tp1=float(reward1), reward_tp2=float(reward2),
        rr_tp1=float(rr1), rr_tp2=float(rr2), geometry_valid=bool(valid),
        reason='VALID_GEOMETRY' if valid else 'INVALID_GEOMETRY',
    )


def size_position_from_stop(*, account_equity: float, risk_pct: float,
                            entry: float, stop: float, atr: float | None = None) -> PositionRiskResult:
    """Compute paper sizing from stop distance; no order execution is performed."""
    if account_equity <= 0 or entry <= 0 or stop <= 0:
        raise ValueError('equity and prices must be positive')
    if not (0 < risk_pct <= 100):
        raise ValueError('risk_pct must be within (0, 100]')
    distance = abs(float(entry) - float(stop))
    if distance <= 0:
        raise ValueError('entry and stop must differ')
    if atr is not None and atr <= 0:
        raise ValueError('atr must be positive when supplied')

    budget = float(account_equity) * (float(risk_pct) / 100.0)
    units = budget / distance
    notional = units * float(entry)
    atr_multiple = distance / float(atr) if atr is not None else None
    return PositionRiskResult(
        account_equity=float(account_equity), risk_pct=float(risk_pct),
        risk_budget=budget, stop_distance=distance, units=units,
        notional=notional, atr=float(atr) if atr is not None else None,
        stop_distance_atr=atr_multiple,
    )
