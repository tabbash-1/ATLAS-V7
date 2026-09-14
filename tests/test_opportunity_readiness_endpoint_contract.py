from pathlib import Path

import opportunity_readiness_boot_patch as boot_patch


INSTALL_BLOCK = (
    'FINAL_TRADE_READY_GUARD = install_final_trade_ready_guard(atlas)\n'
    'if isinstance(getattr(atlas, "WEB_SAFE_MODE", None), dict):\n'
    '    atlas.WEB_SAFE_MODE["final_trade_ready_guard"] = FINAL_TRADE_READY_GUARD\n'
)


def test_boot_patch_exposes_ranked_and_snapshot_readiness_routes(tmp_path, monkeypatch):
    target = tmp_path / "cloud_web_only_final.py"
    target.write_text(
        INSTALL_BLOCK
        + '\nclass Handler:\n'
        + '    def do_GET(self):\n'
        + '        parsed = object()\n'
        + '        if parsed.path == "/api/runtime/status":\n'
        + '            return None\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(boot_patch, "FINAL", target)

    boot_patch.apply()

    patched = target.read_text(encoding="utf-8")
    assert boot_patch.MARKER in patched
    assert 'parsed.path in ("/api/opportunities/ranked", "/api/production/readiness")' in patched
    assert 'return self._json(atlas.opportunity_readiness(symbols))' in patched
    assert 'if parsed.path == "/api/runtime/status":' in patched


def test_snapshot_readiness_path_matches_boot_patch_contract():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/atlas-production-snapshot.yml").read_text(encoding="utf-8")
    patch = (root / "opportunity_readiness_boot_patch.py").read_text(encoding="utf-8")

    assert 'fetch_json readiness /api/production/readiness' in workflow
    assert '"/api/production/readiness"' in patch
