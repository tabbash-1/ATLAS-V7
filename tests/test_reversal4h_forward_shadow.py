import json
from pathlib import Path

from research import reversal4h_forward_shadow as s


def _rows():
    rows=[]
    px=100.0
    for i in range(32):
        if i < 20:
            px += 1.0
        else:
            px -= 1.0
        rows.append({"t":i*s.HOUR_MS,"o":px-0.1,"h":px+0.5,"l":px-0.5,"c":px,"v":100.0})
    return rows


def test_reversal_prediction_fades_meaningful_4h_move():
    rows=_rows()[:20]
    pred,ev=s.reversal4h_prediction(rows)
    assert pred=="SHORT"
    assert ev["recent_4h_side"]=="LONG"
    assert ev["move_4h_atr"]>0


def test_forward_shadow_captures_and_settles_without_production_authority(tmp_path):
    rows=_rows()
    def fetcher(symbol,days,end_ms=None):
        return rows

    ledger=tmp_path/"ledger.json"
    latest=tmp_path/"latest.json"
    a=s.run(now_ms=20*s.HOUR_MS,fetcher=fetcher,ledger_path=str(ledger),latest_path=str(latest))
    assert a["state"]=="FORWARD_SHADOW_COLLECTING"
    assert len(a["new_observation_ids"])==len(s.SYMBOLS)
    assert a["can_override_production"] is False
    assert a["production_effect"]=="NONE"

    b=s.run(now_ms=32*s.HOUR_MS,fetcher=fetcher,ledger_path=str(ledger),latest_path=str(latest))
    assert b["metrics"]["4h"]["n"]==len(s.SYMBOLS)
    assert b["metrics"]["8h"]["n"]==len(s.SYMBOLS)
    assert b["metrics"]["12h"]["n"]==len(s.SYMBOLS)
    assert b["metrics"]["12h"]["directional_precision_pct"]==100.0

    data=json.loads(ledger.read_text())
    btc=next(x for x in data["entries"] if x["symbol"]=="BTCUSDT" and x["decision_at_ms"]==20*s.HOUR_MS)
    assert btc["prediction"]=="SHORT"
    assert btc["outcomes"]["4h"]["actual"]=="SHORT"
    assert btc["outcomes"]["12h"]["correct"] is True
    assert btc["live_execution"] is False
    assert btc["can_override_final_gate"] is False


def test_delayed_job_recovers_latest_aligned_slot_without_future_leakage(tmp_path):
    rows=_rows()
    def fetcher(symbol,days,end_ms=None):
        return rows
    ledger=tmp_path/"l.json"
    x=s.run(now_ms=21*s.HOUR_MS,fetcher=fetcher,ledger_path=str(ledger),latest_path=str(tmp_path/"s.json"))
    assert x["entry_count"]==len(s.SYMBOLS)
    data=json.loads(ledger.read_text())
    btc=next(e for e in data["entries"] if e["symbol"]=="BTCUSDT")
    assert btc["decision_at_ms"]==20*s.HOUR_MS
    assert btc["decision_bar_t"]==19*s.HOUR_MS
    assert btc["capture_lag_minutes"]==60.0
    assert btc["capture_lag_limit_minutes"]==120.0


def test_stale_slot_fails_closed_instead_of_retrospective_backfill(tmp_path):
    rows=_rows()
    def fetcher(symbol,days,end_ms=None):
        return rows
    x=s.run(now_ms=23*s.HOUR_MS,fetcher=fetcher,ledger_path=str(tmp_path/"l.json"),latest_path=str(tmp_path/"s.json"))
    assert x["entry_count"]==0
    assert x["new_observation_ids"]==[]
