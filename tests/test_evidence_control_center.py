import opportunity_replay_shadow as m
import evidence_control_center as c
import opportunity_path_replay as p


def test_replay_hypotheses_are_prelocked_and_shadow_only():
    assert m.MIN_N==30 and m.THRESHOLD==68
    assert len(m.HYPOTHESES)==5
    assert all(x["shadow_action"] in {"SKIP","REPRICE_ENTRY","REPRICE_EXIT"} for x in m.HYPOTHESES)


def test_filter_triggers_are_deterministic():
    assert m._trigger("FUTURES_OPPOSITION_VETO",{"futures_alignment":"OPPOSED"}) is True
    assert m._trigger("BREAKOUT_CONFIRMATION_REQUIRED",{"breakout_confirmed":False}) is True
    assert m._trigger("MARGINAL_THRESHOLD_VETO",{"score":68,"threshold":68}) is True
    assert m._trigger("MARGINAL_THRESHOLD_VETO",{"score":69,"threshold":68}) is False


def test_path_change_hypotheses_are_not_fake_settled():
    path=[x for x in m.HYPOTHESES if x["kind"]=="PATH_CHANGE"]
    assert {x["id"] for x in path}=={"DELAY_ENTRY_1H_CONFIRM","EARLY_MOMENTUM_FAILFAST_EXIT","PROFIT_PROTECTION_TIME_DECAY"}


def test_control_center_contract_is_read_only():
    assert c.THRESHOLD==68
    assert c.FORMAL_SAMPLE==30
    assert c.EPOCH_ID=="HTF_SR_V2_2026-09-14"


def test_production_web_exposes_read_only_control_center_route():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    src=(root/"cloud_web_only_final.py").read_text(encoding="utf-8")
    assert 'parsed.path == "/api/evidence/control-center"' in src
    assert "build_evidence_control_center(BASE)" in src


def test_terminal_links_and_renders_evidence_center():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    index=(root/"index.html").read_text(encoding="utf-8")
    page=(root/"evidence-control-center.html").read_text(encoding="utf-8")
    assert "/evidence-control-center.html" in index
    assert "/api/evidence/control-center" in page
    assert "Opportunity Replay Shadow" in page


def test_path_replay_is_prelocked_shadow_only():
    assert p.ACTIVATION_AT=="2026-09-18T07:10:00+00:00"
    assert p.MIN_N==30 and p.THRESHOLD==68
    assert p.FAILFAST_ADVERSE_R==-0.25 and p.FAILFAST_WINDOW_H==4
    assert {x["id"] for x in p.PATH_HYPOTHESES}=={"DELAY_ENTRY_1H_CONFIRM","EARLY_MOMENTUM_FAILFAST_EXIT"}


def test_control_center_renders_candle_path_replay():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    page=(root/"evidence-control-center.html").read_text(encoding="utf-8")
    source=(root/"evidence_control_center.py").read_text(encoding="utf-8")
    assert "Candle-Path Replay" in page
    assert "path_replay" in source
    assert "opportunity-path-replay-latest.json" in source


def test_control_center_exposes_manual_strategy_review_gate_only():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    source=(root/"evidence_control_center.py").read_text(encoding="utf-8")
    page=(root/"evidence-control-center.html").read_text(encoding="utf-8")
    assert "strategy-change-review-gate-latest.json" in source
    assert "Strategy Change Review Gate" in page
    assert "automatic_promotion" in source


def test_evidence_status_writers_retry_if_main_moves():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/".github/workflows"
    for name in ("atlas-evidence-control-center.yml","atlas-opportunity-path-replay.yml","atlas-strategy-change-review-gate.yml"):
        y=(root/name).read_text(encoding="utf-8")
        assert "for attempt in 1 2 3 4 5" in y
        assert "git fetch origin main" in y
        assert "git rebase origin/main" in y
        assert "main moved during evidence push" in y
