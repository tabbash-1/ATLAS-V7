from pathlib import Path


def test_product_shell_sync_is_installed():
    js=Path('atlas-production-decision.js').read_text()
    assert 'syncProductShell' in js
    assert 'Verified Production plan' in js
    assert 'Conditional Production plan' in js
    assert "canonicalPlan:true" in js
