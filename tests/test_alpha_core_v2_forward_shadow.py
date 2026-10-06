import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/"research"/"alpha_core_v2_forward_shadow.py"
spec=importlib.util.spec_from_file_location("alpha_forward",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def _rows(n):
    out=[];px=100.0
    for i in range(n):
        px += 0.1
        out.append({"t":i*m.HOUR_MS,"o":px-0.05,"h":px+0.2,"l":px-0.2,"c":px,"v":100.0})
    return out


def test_contract_is_research_only():
    assert m.VERSION=="ATLAS_ALPHA_CORE_V2_FORWARD_SHADOW_V2_FRESH_RUNTIME_CAPTURE"
    assert m.HORIZONS==(4,8,12)


def test_capture_is_idempotent_and_settles_forward(monkeypatch,tmp_path):
    monkeypatch.setattr(m,"SYMBOLS",("BTCUSDT",))
    monkeypatch.setattr(m,"alpha_analyze",lambda rows,decision_at,btc,symbol:{
        "decision":"LONG","candidate_direction":"LONG","regime":"TREND",
        "playbook":"TEST","blockers":[],"evidence":["TEST"],
        "evidence_distribution":{"LONG":0.8,"SHORT":0.1,"WAIT":0.1},
        "context":{"atr14":1.0},
    })
    all_rows=_rows(100)
    def fetcher(symbol,days,now_ms):
        return [x for x in all_rows if x["t"]+m.HOUR_MS<=now_ms]

    ledger=tmp_path/"ledger.json"
    latest=tmp_path/"latest.json"
    a=m.run(now_ms=80*m.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert a["entry_count"]==1
    b=m.run(now_ms=82*m.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert b["entry_count"]==1
    assert b["new_observation_ids"]==[]

    c=m.run(now_ms=92*m.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert c["entry_count"]==2
    import json
    data=json.loads(ledger.read_text())
    first=data["entries"][0]
    assert set(first["outcomes"])=={"4h","8h","12h"}
    assert first["live_execution"] is False
    assert first["can_override_production"] is False
    assert first["can_create_trade"] is False



def test_scheduler_delay_still_captures_fresh_runtime_state(monkeypatch,tmp_path):
    monkeypatch.setattr(m,"SYMBOLS",("BTCUSDT",))
    monkeypatch.setattr(m,"alpha_analyze",lambda rows,decision_at,btc,symbol:{
        "decision":"WAIT","candidate_direction":None,"regime":"TRANSITION",
        "playbook":None,"blockers":["TEST"],"evidence":[],
        "evidence_distribution":{"LONG":0.2,"SHORT":0.2,"WAIT":0.6},
        "context":{"atr14":1.0},
    })
    all_rows=_rows(100)
    def fetcher(symbol,days,now_ms):
        return [x for x in all_rows if x["t"]+m.HOUR_MS<=now_ms]

    ledger=tmp_path/"ledger.json"; latest=tmp_path/"latest.json"
    x=m.run(now_ms=83*m.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert x["entry_count"]==1
    import json
    row=json.loads(ledger.read_text())["entries"][0]
    assert row["decision_at_ms"]==83*m.HOUR_MS
    assert row["decision_bar_t"]==82*m.HOUR_MS
    assert row["capture_lag_minutes"]==0.0
    assert row["minimum_capture_spacing_minutes"]==240.0
