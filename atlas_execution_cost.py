from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionCostResult:
    expected_move_bps: float
    modeled_cost_bps: float
    required_edge_bps: float
    net_edge_bps: float
    passed: bool
    reason: str


def evaluate_execution_cost(*, expected_move_bps: float, fee_bps: float,
                            spread_bps: float, slippage_bps: float,
                            funding_bps: float = 0.0,
                            safety_multiplier: float = 1.25) -> ExecutionCostResult:
    """Evaluate whether expected movement is large enough after modeled costs.

    This is deterministic analysis only. It does not place orders and does not
    alter any Production threshold or FINAL_TRADE_GATE behavior.
    """
    values = (expected_move_bps, fee_bps, spread_bps, slippage_bps, funding_bps)
    if any(v < 0 for v in values):
        raise ValueError('cost and expected-move inputs must be non-negative')
    if safety_multiplier < 1.0:
        raise ValueError('safety_multiplier must be >= 1.0')
    modeled = float(fee_bps + spread_bps + slippage_bps + funding_bps)
    required = modeled * float(safety_multiplier)
    net_edge = float(expected_move_bps) - modeled
    passed = float(expected_move_bps) > required
    reason = 'EDGE_AFTER_COST' if passed else 'INSUFFICIENT_EDGE_AFTER_COST'
    return ExecutionCostResult(
        expected_move_bps=float(expected_move_bps),
        modeled_cost_bps=modeled,
        required_edge_bps=required,
        net_edge_bps=net_edge,
        passed=passed,
        reason=reason,
    )
