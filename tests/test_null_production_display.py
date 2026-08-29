from pathlib import Path


def test_null_production_metrics_are_not_rendered_as_zero():
    js = Path('production-null-display-fix.js').read_text(encoding='utf-8')
    assert "v!==null&&v!==undefined&&v!==''" in js
    assert "score unavailable because no directional Production candidate was scored" in js
    assert "R:R unavailable" in js
    assert "V1_NULL_IS_NOT_ZERO" in js


def test_null_display_guard_loads_after_product_shell():
    js = Path('theme-toggle.js').read_text(encoding='utf-8')
    product = js.index("'atlas-product-shell.js'")
    guard = js.index("'production-null-display-fix.js'")
    assert guard > product
