from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
shell = (ROOT / 'atlas-product-shell.js').read_text()
theme = (ROOT / 'theme-toggle.js').read_text()

assert 'ATLAS_PRODUCT_SHELL_V2_SINGLE_AUTHORITY' in shell
assert "Canonical Production: 1H" in shell
assert "Production score · 1H" in shell
assert "window.ATLAS_PRODUCTION_SNAPSHOT_GUARD" in shell
assert "window.ATLAS_MASTER" not in shell, 'Product shell must not fall back to local/research master state'
assert "new MutationObserver(()=>requestAnimationFrame(update)).observe(document.body" not in shell, 'Do not install a broad self-triggering body observer'
assert "fetch(`/api/decision/current" not in shell, 'Product shell must delegate Production verification to the single verifier'
assert "window.ATLAS_PRODUCTION_DECISION_UI" in shell

scripts_line = next(line for line in theme.splitlines() if 'const scripts=' in line)
assert scripts_line.rfind('atlas-product-shell.js') > scripts_line.find('atlas-ai-ui.js')
assert scripts_line.rstrip().endswith("'atlas-product-shell.js'];")

print('product shell single-authority invariants: OK')
