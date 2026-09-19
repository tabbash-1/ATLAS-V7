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


def test_semantics_are_owned_by_canonical_product_writer():
    loader = Path('theme-toggle.js').read_text(encoding='utf-8')
    autoload = Path('production-web-autoload.js').read_text(encoding='utf-8')
    assert "const scripts=['atlas-product-shell.js']" in loader
    assert "'production-semantics-labels.js'" not in loader
    assert "Final Trade Gate" in autoload
    assert "No user-facing trade geometry while canonical decision is WAIT" in autoload
