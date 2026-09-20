from pathlib import Path


def test_unified_command_center_removes_literal_script_separator():
    source = Path("atlas-unified-command-center.js").read_text(encoding="utf-8")
    assert "function removeLiteralScriptSeparator()" in source
    assert "previous.nodeType===Node.TEXT_NODE" in source
    assert "previous.remove()" in source
    assert "removeLiteralScriptSeparator();" in source
