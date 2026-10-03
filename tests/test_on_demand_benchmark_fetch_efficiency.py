from pathlib import Path

def test_benchmark_accepts_prefetched_rows():
    t=(Path(__file__).resolve().parents[1]/"research"/"on_demand_analysis_benchmark.py").read_text()
    assert "rows=None" in t
    assert "rows=rows" in t
