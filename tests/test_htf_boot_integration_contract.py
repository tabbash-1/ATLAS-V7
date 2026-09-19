from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_boot_patch_installs_htf_before_quality_gate_wraps_production():
    boot = (ROOT / 'render_boot_patch.py').read_text(encoding='utf-8')
    web = (ROOT / 'cloud_web_only.py').read_text(encoding='utf-8')

    assert 'HTF_STRUCTURAL_THESIS_BOOT_PATCH_V1' in boot
    assert 'from htf_structural_thesis import install as _install_htf_structural_thesis' in boot
    assert '_install_htf_structural_thesis(atlas)' in boot
    assert 'patch_product_quality_gate_htf_install()' in boot

    # Render mutates the quality-gate source before collector_server and the
    # quality gate are imported, so the final quality gate wraps the HTF gate.
    assert web.index('apply_render_boot_patch()') < web.index('import collector_server as atlas')
    assert web.index('apply_render_boot_patch()') < web.index('from product_quality_gate_overlay import install as install_product_quality_gate')
    assert web.index('install_canonical_geometry(atlas)') < web.index('install_product_quality_gate(atlas)')


def test_render_web_installs_htf_sr_v2_before_quality_and_final_gate():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    web=(root/"cloud_start_web.py").read_text(encoding="utf-8")
    assert "from htf_sr_decision_v2 import install as _install_htf_sr_decision_v2" in web
    assert "_install_htf_sr_decision_v2(_collector)" in web
    assert web.index("_install_htf_core_geometry(_collector)") < web.index("_install_htf_sr_decision_v2(_collector)") < web.index("_install_product_quality_gate(_collector)")
