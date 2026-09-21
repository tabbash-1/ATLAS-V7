import ast
from pathlib import Path

def test_decision_api_emits_independent_regime_without_using_candidate():
    src=Path("production_decision_api.py").read_text()
    tree=ast.parse(src)
    assert "independent_regime_analyze(symbol, ks, btc)" in src
    assert "'independent_market_regime':independent_regime.get('asset')" in src
    assert "'independent_btc_regime':independent_regime.get('btc')" in src
    # Regime computation must precede Production scorer/candidate construction.
    assert src.index("independent_regime = independent_regime_analyze") < src.index("row=atlas.cloud_score_symbol")
