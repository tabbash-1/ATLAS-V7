from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_homepage_is_direct_coin_analyzer():
    text=(ROOT/"index.html").read_text(encoding="utf-8")
    assert "هل أشتري أم أبيع؟" in text
    assert "/api/decision/current?symbol=" in text
    assert "/api/deep-analysis/current?symbol=" in text
    assert "Advanced Terminal" in text
    assert "advanced-terminal.html" in text
    assert "BUY" in text and "SELL" in text and "WAIT" in text


def test_advanced_terminal_preserves_full_existing_workspace():
    text=(ROOT/"advanced-terminal.html").read_text(encoding="utf-8")
    assert "ATLAS V7 — Institutional Crypto Intelligence Terminal" in text
    assert "PRODUCTION DECISION" in text
    assert "atlas-unified-command-center.js" in text


def test_simple_homepage_does_not_boot_research_dashboard_scripts():
    text=(ROOT/"index.html").read_text(encoding="utf-8")
    for script in (
        "profitability-shadow-ui.js",
        "smart-money-validation-ui.js",
        "promotion-gate-ui.js",
        "performance-dashboard-ui.js",
        "pattern-memory-ui.js",
    ):
        assert script not in text
