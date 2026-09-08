from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'collector_server.py'
text = SRC.read_text(encoding='utf-8')


def test_canonical_forward_contract_is_explicit():
    assert "CANONICAL_FORWARD_HORIZONS=(4,8,12)" in text
    assert "CANONICAL_DECISION_SCHEMA='ATLAS_CANONICAL_DECISION_TRUTH_V1'" in text
    assert "CANONICAL_DECISION_SOURCE='FINAL_TRADE_GATE'" in text
    assert 'def _is_canonical_forward_row(row):' in text


def test_forward_observation_freezes_canonical_decision():
    assert "incoming_execution=_is_canonical_forward_row(payload)" in text
    assert "if incoming_execution and not _is_canonical_forward_row(old):" in text
    assert "'canonical_decision','canonical_decision_id','canonical_wait_reason'" in text
    assert "row['schema']='ATLAS_FORWARD_V2_CANONICAL_FREEZE'" in text
    assert "row['decision_source_of_truth']=CANONICAL_DECISION_SOURCE" in text
    assert "row['evaluation_horizons_h']=list(CANONICAL_FORWARD_HORIZONS)" in text


def test_8h_is_prospective_canonical_only():
    assert "horizons=HORIZONS + ((8,) if _is_canonical_forward_row(r) else ())" in text
    assert "for h in horizons:" in text
    assert "legacy 1/4/12/24; canonical rows add 8h prospectively only" in text


if __name__ == '__main__':
    test_canonical_forward_contract_is_explicit()
    test_forward_observation_freezes_canonical_decision()
    test_8h_is_prospective_canonical_only()
    print('canonical forward freeze contract tests: ok')
