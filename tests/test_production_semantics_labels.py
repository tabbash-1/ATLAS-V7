from pathlib import Path


def test_semantic_labels_distinguish_candidate_from_canonical_geometry():
    js = Path('production-semantics-labels.js').read_text(encoding='utf-8')
    assert 'Candidate / qualification R:R' in js
    assert 'Canonical Production R:R' in js
    assert 'failed the execution gate · no canonical Production trade plan' in js


def test_regime_label_explains_bias_and_pullback_without_changing_engine():
    js = Path('production-semantics-labels.js').read_text(encoding='utf-8')
    assert "pb.includes('PULLBACK_LONG')" in js
    assert "pb.includes('PULLBACK_SHORT')" in js
    assert 'LONG BIAS · PULLBACK' in js
    assert 'SHORT BIAS · PULLBACK' in js


def test_semantics_layer_is_loaded_after_product_shell():
    loader = Path('theme-toggle.js').read_text(encoding='utf-8')
    product = loader.index("'atlas-product-shell.js'")
    semantics = loader.index("'production-semantics-labels.js'")
    assert semantics > product
