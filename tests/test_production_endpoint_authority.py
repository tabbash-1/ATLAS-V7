from pathlib import Path

src = Path('production_decision_api.py').read_text()
assert "result=atlas.production_decision(symbol)" in src, 'endpoint must call canonical wrapped atlas.production_decision'
assert "result=build_decision(symbol); return self._json" not in src, 'endpoint must not bypass downstream decision engine wrappers'

ui = Path('theme-toggle.js').read_text()
assert "const scripts=['atlas-product-shell.js']" in ui, 'Production shell must be the only optional writer loaded into the product surface'
for legacy in ('atlas-ai-analysis-layer.js','atlas-decision-quality.js','atlas-ai-ui.js','production-null-display-fix.js','production-semantics-labels.js'):
    assert legacy not in ui.split('const scripts=',1)[1], f'legacy writer still loaded: {legacy}'

print('production endpoint authority tests: ok')
