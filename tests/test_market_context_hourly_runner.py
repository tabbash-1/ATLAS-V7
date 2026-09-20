import json
import market_context_hourly_runner as r

def test_runner_is_research_only(tmp_path,monkeypatch):
 monkeypatch.setattr(r,"LEDGER",tmp_path/"ledger.jsonl")
 monkeypatch.setattr(r,"SNAP",tmp_path/"decisions.json")
 r.SNAP.write_text(json.dumps({"decisions":{"BTCUSDT":{"decision":"WAIT","candidate_direction":"LONG"}}}))
 monkeypatch.setattr(r.cycle.universe,"symbols",lambda:("BTCUSDT",))
 monkeypatch.setattr(r,"_klines",lambda s:[{"close":100+i*.01} for i in range(200)])
 monkeypatch.setattr(r,"_price_at",lambda s,d:101)
 monkeypatch.setattr(r.evaluator,"OUT",tmp_path/"eval.json")
 monkeypatch.setattr(r.status,"OUT",tmp_path/"status.json")
 monkeypatch.setattr(r.status.evaluator,"LEDGER",r.LEDGER)
 settlements=tmp_path/"settlements.jsonl"
 monkeypatch.setattr(r.settlement.ledger,"SETTLEMENT_OUT",settlements)
 monkeypatch.setattr(r.evaluator,"SETTLEMENTS",settlements)
 monkeypatch.setattr(r.status.evaluator,"SETTLEMENTS",settlements)
 x=r.run(__import__("datetime").datetime(2026,9,20,tzinfo=__import__("datetime").timezone.utc))
 assert x["research_only"] is True and x["production_effect"]=="NONE"
