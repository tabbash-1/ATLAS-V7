import importlib.util
from pathlib import Path
import subprocess
import sys

P=Path(__file__).resolve().parents[1]/"research"/"on_demand_analysis_benchmark.py"
spec=importlib.util.spec_from_file_location("bench",P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_product_contract_is_analysis_not_trade_discovery():
    assert m.VERSION=="ATLAS_ON_DEMAND_ANALYSIS_BENCHMARK_V6_ALPHA_CORE_V2"
    assert m.HORIZONS==(4,8,12)


def _trend_rows(side="LONG", n=801):
    sign=1 if side=="LONG" else -1
    px=100.0
    rows=[]
    pattern=(0.12,-0.08,0.12)
    for i in range(n):
        px += sign*pattern[i%3]
        rows.append({
            "t":i*m.HOUR_MS,
            "o":px-sign*0.03,
            "h":px+0.6,
            "l":px-0.6,
            "c":px,
            "v":100.0,
        })
    return rows


def test_market_behavior_probes_distinguish_continuation_from_reversal(monkeypatch):
    rows=_trend_rows("LONG",n=100)
    monkeypatch.setattr(m,"atr",lambda *_:0.5)
    assert m.momentum_4h_probe(rows)=="LONG"
    assert m.reversal_4h_probe(rows)=="SHORT"
    assert m.momentum_12h_probe(rows)=="LONG"
    assert m.reversal_12h_probe(rows)=="SHORT"


def test_market_behavior_probe_waits_inside_atr_deadband(monkeypatch):
    rows=_trend_rows("LONG",n=100)
    monkeypatch.setattr(m,"atr",lambda *_:1000.0)
    assert m.momentum_4h_probe(rows)=="WAIT"
    assert m.reversal_12h_probe(rows)=="WAIT"


def test_12h_thesis_4h_pullback_probe_emits_thesis_direction(monkeypatch):
    rows=[]
    px=100.0
    for i in range(20):
        if i < 16:
            px += 1.0
        else:
            px -= 0.5
        rows.append({"t":i*m.HOUR_MS,"o":px,"h":px+0.2,"l":px-0.2,"c":px,"v":100.0})
    monkeypatch.setattr(m,"atr",lambda *_:1.0)
    assert m._recent_move_side(rows,12)=="LONG"
    assert m._recent_move_side(rows,4)=="SHORT"
    assert m.thesis12_pullback4_probe(rows)=="LONG"


def test_12h_thesis_4h_pullback_probe_avoids_chasing(monkeypatch):
    rows=[]
    px=100.0
    for i in range(20):
        px += 1.0
        rows.append({"t":i*m.HOUR_MS,"o":px,"h":px+0.2,"l":px-0.2,"c":px,"v":100.0})
    monkeypatch.setattr(m,"atr",lambda *_:1.0)
    assert m._recent_move_side(rows,12)=="LONG"
    assert m._recent_move_side(rows,4)=="LONG"
    assert m.thesis12_pullback4_probe(rows)=="WAIT"


def test_professional_challenger_accepts_aligned_top_down_long():
    alt=_trend_rows("LONG")
    btc=_trend_rows("LONG")
    as_of=alt[-1]["t"]+m.HOUR_MS
    assert m.analyst_stack_v2(alt,as_of,btc,"ETHUSDT")=="LONG"


def test_professional_challenger_btc_first_blocks_opposed_alt():
    alt=_trend_rows("LONG")
    btc=_trend_rows("SHORT")
    as_of=alt[-1]["t"]+m.HOUR_MS
    assert m.analyst_stack_v2(alt,as_of,btc,"ETHUSDT")=="WAIT"


def test_professional_challenger_rejects_late_extension():
    alt=_trend_rows("LONG")
    btc=_trend_rows("LONG")
    alt[-1]=dict(alt[-1])
    alt[-1]["c"] += 8.0
    alt[-1]["h"] = alt[-1]["c"] + 0.6
    alt[-1]["o"] = alt[-1]["c"] - 0.2
    as_of=alt[-1]["t"]+m.HOUR_MS
    assert m.analyst_stack_v2(alt,as_of,btc,"ETHUSDT")=="WAIT"

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
    assert x["opposite_direction_pct_of_calls"]==0.0

def test_temporal_thirds_keep_timestamp_groups_intact():
    records=[]
    for t in range(9):
        for symbol in ("BTCUSDT","ETHUSDT"):
            records.append({"t":t,"symbol":symbol,"prediction":"LONG","actual":"LONG"})
    x=m.temporal_thirds(records)
    assert x["early"]["n"]==6
    assert x["middle"]["n"]==6
    assert x["late"]["n"]==6
    assert x["early"]["directional_precision_pct"]==100.0
    assert x["late"]["directional_precision_pct"]==100.0


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


def test_alpha_core_v2_is_in_same_benchmark_and_research_only():
    assert "alpha_core_v2" in m.run.__code__.co_consts or hasattr(m,"alpha_core_v2_engine")
    assert m.alpha_core_v2_engine([],0,[],"BTCUSDT")=="WAIT"
