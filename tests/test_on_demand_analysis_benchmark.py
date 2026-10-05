import importlib.util
from pathlib import Path
import subprocess
import sys

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


def _candles(timestamps):
    return [{"t":t,"o":float(i+1),"h":float(i+2),"l":float(i),"c":float(i+1.5),"v":1.0}
            for i,t in enumerate(timestamps)]

def test_resample_closed_excludes_open_htf_bar():
    rows=_candles([i*m.HOUR_MS for i in range(12)])
    assert len(m.resample_closed(rows,4,4*m.HOUR_MS))==1
    assert len(m.resample_closed(rows,12,11*m.HOUR_MS))==0
    assert len(m.resample_closed(rows,12,12*m.HOUR_MS))==1

def test_resample_closed_rejects_gaps_in_htf_bar():
    rows=_candles([i*m.HOUR_MS for i in range(12) if i!=5])
    bars=m.resample_closed(rows,12,12*m.HOUR_MS)
    assert bars==[]


def test_benchmark_is_scheduled_by_actions_not_render_boot():
    root=Path(__file__).resolve().parents[1]
    boot=(root/"render_boot_patch.py").read_text()
    workflow=(root/".github"/"workflows"/"on-demand-analysis-benchmark.yml").read_text()
    assert "subprocess.run(" not in boot
    assert "on_demand_analysis_benchmark.py" not in boot
    assert "push:" in workflow and "pull_request:" in workflow and "branches: [main]" in workflow
    assert "python -m pip install pytest" in workflow


def test_benchmark_cli_imports_repository_module_from_script_path():
    root=P.parents[1]
    result=subprocess.run([sys.executable,str(P),"--help"],cwd=root,capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    assert "--days" in result.stdout
