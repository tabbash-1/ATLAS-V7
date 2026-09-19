from pathlib import Path


def test_null_production_metrics_are_not_rendered_as_zero():
    js = Path('production-web-autoload.js').read_text(encoding='utf-8')
    assert "v!==null&&v!==undefined&&v!==''" in js
    assert "score===null?'—':score" in js
    assert "actionable?fmt(a.entry):'—'" in js
    assert "actionable?`${fmt(a.take_profit)} · R:R ${fmt(a.risk_reward,2)}`:'—'" in js


def test_null_display_is_owned_by_single_product_writer():
    js = Path('theme-toggle.js').read_text(encoding='utf-8')
    assert "const scripts=['atlas-product-shell.js']" in js
    assert "'production-null-display-fix.js'" not in js
