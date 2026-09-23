import pathlib
p=pathlib.Path(".github/workflows/atlas-production-snapshot.yml").read_text()
assert "python3 build_trade_edge_prospective_report.py" in p
assert p.count("status/trade-edge-prospective-latest.json") >= 4
assert "historical_rows_excluded == true" in p
assert "can_override_production == false" in p
