"""Regression for prospective-only ADP V8 capture; no trading-rule changes."""
import ast
import statistics
from pathlib import Path

SOURCE = Path("research/adp/v8_forward_shadow.py")


def _functions():
    tree = ast.parse(SOURCE.read_text())
    wanted = [node for node in tree.body
              if isinstance(node, ast.FunctionDef)
              and node.name in {"eligible_forward", "horizon_stats"}]
    assert {n.name for n in wanted} == {"eligible_forward", "horizon_stats"}
    namespace = {"statistics": statistics}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def _row(t=1_800_000_000_000, capture_delta=3_600_001, **changes):
    row = {"id": "BTCUSDT:test", "symbol": "BTCUSDT",
           "signal_t": t, "captured_at_ms": t + capture_delta,
           "capture_kind": "LIVE_HOURLY_CLOSED_CANDLE",
           "outcomes": {"4h": {"net_pct": 1.0},
                        "8h": {"net_pct": -0.5},
                        "12h": {"net_pct": -2.0}}}
    row.update(changes)
    return row


def test_forward_provenance_rejects_legacy_backfill_and_bad_capture():
    eligible = _functions()["eligible_forward"]
    assert eligible(_row())
    assert eligible(_row(capture_delta=3_600_000))
    for row in (
        _row(captured_at_ms=None),
        _row(capture_kind="BACKFILL"),
        _row(capture_delta=3_599_999),
        _row(capture_delta=7_200_000),
        _row(signal_t="1800000000000"),
        _row(captured_at_ms=True),
    ):
        assert not eligible(row), row


def test_only_verified_rows_contribute_to_horizon_metrics():
    fns = _functions()
    verified = [r for r in [_row(), _row(captured_at_ms=None)]
                if fns["eligible_forward"](r)]
    assert len(verified) == 1
    assert fns["horizon_stats"](verified, 4)["net_expectancy_pct"] == 1
    assert fns["horizon_stats"](verified, 8)["profit_factor"] == 0
    assert fns["horizon_stats"](verified, 12)["max_arithmetic_drawdown_pctpoints"] == 2
    assert fns["horizon_stats"]([], 12)["net_expectancy_pct"] is None


def test_capture_and_readiness_wiring_remains_prospective_only():
    src = SOURCE.read_text()
    assert 't!=now-3600000' in src
    assert '"captured_at_ms":captured_ms' in src
    assert 'verified=[r for r in rows if eligible_forward(r)]' in src
    assert 'for r in verified if "12h" in r["outcomes"]' in src
    assert 'len(vals)>=500' in src
    assert 'production_effect":"NONE"' in src
