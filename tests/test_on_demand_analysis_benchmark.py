import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/"research"/"on_demand_analysis_benchmark.py"
spec=importlib.util.spec_from_file_location("bench",P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_product_contract_is_analysis_not_trade_discovery():
    assert m.VERSION.startswith("ATLAS_ON_DEMAND_ANALYSIS_BENCHMARK_")
    assert m.HORIZONS==(4,8,12)

def test_metrics_distinguish_wait_from_wrong_direction():
    rows=[
      {"prediction":"WAIT","actual":"LONG"},
      {"prediction":"LONG","actual":"LONG"},
      {"prediction":"SHORT","actual":"WAIT"},
      {"prediction":"WAIT","actual":"WAIT"},
    ]
    x=m.metrics(rows)
    assert x["n"]==4
    assert x["accuracy_pct"]==50.0
    assert x["wait_rate_pct"]==50.0
    assert x["missed_directional_move_pct"]==25.0
    assert x["false_directional_call_pct"]==25.0
    assert x["directional_precision_pct"]==50.0

def test_future_label_has_real_wait_deadband(monkeypatch):
    rows=[{"c":100.0,"h":101.0,"l":99.0} for _ in range(20)]
    rows[18]["c"]=100.1
    monkeypatch.setattr(m,"atr",lambda *_:2.0)
    assert m.future_label(rows,14,4)=="WAIT"
    rows[18]["c"]=101.0
    assert m.future_label(rows,14,4)=="LONG"
    rows[18]["c"]=99.0
    assert m.future_label(rows,14,4)=="SHORT"
