from pathlib import Path


WORKFLOW = Path('.github/workflows/atlas-production-snapshot.yml')
CANONICAL = "['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ZECUSDT','ADAUSDT','LINKUSDT','AVAXUSDT','LTCUSDT']"


def test_snapshot_reports_only_canonical_assets_as_supported():
    text = WORKFLOW.read_text()
    assert f"core_symbols={CANONICAL}" in text
    assert "'supported_assets':core_symbols" in text
    assert "'supported_assets':symbols" not in text


def test_hype_is_explicitly_extra_monitored_not_production_supported():
    text = WORKFLOW.read_text()
    assert "'extra_monitored_symbols':['HYPEUSDT']" in text
    assert "symbols=core_symbols+['HYPEUSDT']" in text


def test_expected_hype_rejection_does_not_count_as_production_failure():
    text = WORKFLOW.read_text()
    assert "production_failures=[x for x in failures if x.get('symbol') in core_symbols]" in text
    assert "'failed_count':len(production_failures)" in text
    assert "'failures':production_failures" in text
