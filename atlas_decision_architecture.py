from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CORE_ASSETS = ('BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','ADAUSDT','LINKUSDT','AVAXUSDT','LTCUSDT')
PRODUCT_HORIZON = '4-12H'
EVALUATION_HORIZONS_H = (4, 8, 12)
PRODUCTION_THRESHOLD = 68

@dataclass(frozen=True)
class LayerResult:
    state: str
    passed: bool
    confidence: float = 0.0
    reasons: List[str] = field(default_factory=list)
    freshness_ok: bool = True
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DecisionArchitectureResult:
    decision: str
    candidate_direction: Optional[str]
    trade_ready: bool
    score: float
    blocking_gates: List[str]
    layers: Dict[str, LayerResult]
    product_horizon: str = PRODUCT_HORIZON
    evaluation_horizons_h: tuple = EVALUATION_HORIZONS_H
    source_of_truth: str = 'FINAL_TRADE_GATE'
    production_threshold: int = PRODUCTION_THRESHOLD


def evaluate_staged_decision(*, candidate_direction: Optional[str], score: float,
                             regime: LayerResult, htf: LayerResult, flow: LayerResult,
                             trigger_1h: LayerResult, cost_liquidity: LayerResult,
                             volatility_risk: LayerResult) -> DecisionArchitectureResult:
    """Pure staged gate. It never fetches market data or executes trades.

    Mandatory layers fail closed. Score can only rank/confirm a structurally
    valid setup and can never bypass a failed gate.
    """
    direction = candidate_direction if candidate_direction in {'LONG', 'SHORT'} else None
    layers = {
        'regime': regime,
        'htf_direction': htf,
        'flow_confirmation': flow,
        'trigger_1h': trigger_1h,
        'cost_liquidity': cost_liquidity,
        'volatility_risk': volatility_risk,
    }
    blocking = []
    if direction is None:
        blocking.append('NO_DIRECTIONAL_CANDIDATE')
    for name, layer in layers.items():
        if not layer.passed or not layer.freshness_ok:
            blocking.append(name.upper())
    if score < PRODUCTION_THRESHOLD:
        blocking.append('SCORE_BELOW_PRODUCTION_THRESHOLD')
    trade_ready = not blocking
    return DecisionArchitectureResult(
        decision=direction if trade_ready else 'WAIT',
        candidate_direction=direction,
        trade_ready=trade_ready,
        score=float(score),
        blocking_gates=blocking,
        layers=layers,
    )
