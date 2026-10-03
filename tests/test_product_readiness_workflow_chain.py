from pathlib import Path

WORKFLOW = Path(".github/workflows/atlas-production-validation-scorecard.yml")


def _text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_readiness_is_built_after_validation_scorecard():
    text = _text()
    score = text.index("python production_validation_scorecard.py")
    readiness = text.index("python atlas_product_readiness_gate.py")
    verify = text.index("Verify isolation and truth contract")
    assert score < readiness < verify


def test_readiness_sources_trigger_owner_workflow():
    text = _text()
    assert "'atlas_product_readiness_gate.py'" in text
    assert "'tests/test_atlas_product_readiness_gate.py'" in text
    assert "'status/canonical-outcomes-latest.json'" in text
    assert "'status/quick-trade-outcomes.json'" in text


def test_validation_and_readiness_publish_atomically():
    text = _text()
    assert "'status/production-validation-latest.json' \\" in text
    assert "'status/product-readiness-latest.json'" in text
    assert "historical_post_v2_excluded_from_current_readiness" in text
    assert "CURRENT_GEOMETRY_V6_EVIDENCE" in text
