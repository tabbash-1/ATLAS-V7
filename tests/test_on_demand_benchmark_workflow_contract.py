from pathlib import Path
import yaml

def test_on_demand_benchmark_runs_and_persists_on_main():
    p=Path(__file__).resolve().parents[1]/".github"/"workflows"/"on-demand-analysis-benchmark.yml"
    raw=p.read_text()
    assert "ref: research/on-demand-analysis-benchmark-v1" not in raw
    assert "git push origin HEAD:main" in raw
    assert 'production_effect=="NONE"' in raw
    assert 'can_override_production==false' in raw
