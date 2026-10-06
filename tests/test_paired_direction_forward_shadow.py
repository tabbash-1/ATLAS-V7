import json
from pathlib import Path

from research import paired_direction_forward_shadow as p


def _rows(n=100, drift=0.2):
    rows=[];px=100.0
    for i in range(n):
        px += drift
        rows.append({"t":i*p.HOUR_MS,"o":px-0.05,"h":px+0.4,"l":px-0.4,"c":px,"v":100.0})
    return rows


def test_contract_is_research_only():
    assert p.VERSION=="ATLAS_PAIRED_DIRECTION_FORWARD_SHADOW_V1"
    assert p.HORIZONS==(4,8,12)


def test_paired_shadow_uses_same_timestamp_for_both_models(monkeypatch,tmp_path):
    monkeypatch.setattr(p,"SYMBOLS",("BTCUSDT",))
    monkeypatch.setattr(p,"reversal4h_prediction",lambda rows:("SHORT",{"atr14":1.0,"reason":"TEST"}))
    monkeypatch.setattr(p,"alpha_analyze",lambda rows,decision_at,btc,symbol:{
        "decision":"LONG","candidate_direction":"LONG","regime":"TREND","playbook":"TEST",
        "blockers":[],"evidence":["TEST"],
    })
    all_rows=_rows()
    def fetcher(symbol,days,now_ms):
        return [x for x in all_rows if x["t"]+p.HOUR_MS<=now_ms]

    ledger=tmp_path/"ledger.json";latest=tmp_path/"latest.json"
    x=p.run(now_ms=80*p.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert x["entry_count"]==1
    row=json.loads(ledger.read_text())["entries"][0]
    assert row["decision_at_ms"]==80*p.HOUR_MS
    assert row["reversal4h"]["prediction"]=="SHORT"
    assert row["alpha_core_v2"]["prediction"]=="LONG"
    assert row["production_effect"]=="NONE"
    assert row["can_create_trade"] is False


def test_pair_settles_head_to_head(monkeypatch,tmp_path):
    monkeypatch.setattr(p,"SYMBOLS",("BTCUSDT",))
    monkeypatch.setattr(p,"reversal4h_prediction",lambda rows:("SHORT",{"atr14":1.0,"reason":"TEST"}))
    monkeypatch.setattr(p,"alpha_analyze",lambda rows,decision_at,btc,symbol:{
        "decision":"LONG","candidate_direction":"LONG","regime":"TREND","playbook":"TEST",
        "blockers":[],"evidence":["TEST"],
    })
    all_rows=_rows(110,drift=0.2)
    def fetcher(symbol,days,now_ms):
        return [x for x in all_rows if x["t"]+p.HOUR_MS<=now_ms]

    ledger=tmp_path/"ledger.json";latest=tmp_path/"latest.json"
    p.run(now_ms=80*p.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    x=p.run(now_ms=92*p.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert x["metrics"]["4h"]["head_to_head"]["n_disagreements"]>=1
    assert x["metrics"]["4h"]["head_to_head"]["alpha_only_correct"]>=1
    assert x["metrics"]["4h"]["head_to_head"]["reversal_only_correct"]==0
    assert x["metrics"]["12h"]["alpha_core_v2"]["directional_precision_pct"]==100.0


def test_four_hour_spacing_prevents_duplicate_market_states(monkeypatch,tmp_path):
    monkeypatch.setattr(p,"SYMBOLS",("BTCUSDT",))
    monkeypatch.setattr(p,"reversal4h_prediction",lambda rows:("WAIT",{"atr14":1.0,"reason":"TEST"}))
    monkeypatch.setattr(p,"alpha_analyze",lambda rows,decision_at,btc,symbol:{
        "decision":"WAIT","candidate_direction":None,"regime":"TRANSITION","playbook":None,
        "blockers":["TEST"],"evidence":[],
    })
    all_rows=_rows()
    def fetcher(symbol,days,now_ms):
        return [x for x in all_rows if x["t"]+p.HOUR_MS<=now_ms]

    ledger=tmp_path/"ledger.json";latest=tmp_path/"latest.json"
    a=p.run(now_ms=80*p.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    b=p.run(now_ms=82*p.HOUR_MS,fetcher=fetcher,ledger_path=ledger,latest_path=latest)
    assert a["entry_count"]==1
    assert b["entry_count"]==1
    assert b["new_observation_ids"]==[]
