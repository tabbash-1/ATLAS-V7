from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
shell = (ROOT / 'atlas-product-shell.js').read_text()
theme = (ROOT / 'theme-toggle.js').read_text()

assert 'ATLAS_PRODUCT_SHELL_V7_BOUND_ANALYST_GEOMETRY' in shell
assert "Final Decision · 4–12H" in shell
assert "Analysis score" in shell
assert "window.ATLAS_PRODUCTION_SNAPSHOT_GUARD" in shell
assert "window.ATLAS_MASTER" not in shell, 'Product shell must not fall back to local/research master state'
assert "new MutationObserver(()=>requestAnimationFrame(update)).observe(document.body" not in shell, 'Do not install a broad self-triggering body observer'
assert "fetch(`/api/decision/current" not in shell, 'Product shell must delegate Production verification to the single verifier'
assert "window.ATLAS_PRODUCTION_DECISION_UI" in shell

scripts_line = next(line for line in theme.splitlines() if 'const scripts=' in line)
assert scripts_line.strip() == "const scripts=['atlas-product-shell.js'];"

print('product shell single-authority invariants: OK')
