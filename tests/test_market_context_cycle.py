import json
import market_context_cycle as c

def test_cycle_captures_universe_without_production_effect(tmp_path,monkeypatch):
 monkeypatch.setattr(c.universe,"symbols",lambda:("ZECUSDT","BTCUSDT"))
 snap={"decisions":{"ZECUSDT":{"decision":"WAIT","candidate_direction":"LONG","htf_thesis":{"frames":{"4H":{"direction":"LONG"},"12H":{"direction":"LONG"}}}},"BTCUSDT":{"decision":"WAIT","candidate_direction":"SHORT","htf_thesis":{"frames":{"4H":{"direction":"SHORT"},"12H":{"direction":"LONG"}}}}}}
 def load(s):
  return [{"close":100+i*.1} for i in range(200)]
 p=tmp_path/"ledger.jsonl";x=c.run(snapshot=snap,kline_loader=load,now="2026-09-20T00:00:00Z",output=p)
 assert x["captured_n"]==2 and x["failed_n"]==0
 assert x["production_effect"]=="NONE" and x["live_execution"] is False
 rows=[json.loads(z) for z in p.read_text().splitlines()]
 assert rows[0]["champion_decision"]=="WAIT"
 assert rows[1]["challenger_decision"]=="WAIT" # HTF conflict preserved

def test_cycle_records_provider_failure_instead_of_inventing_data(tmp_path,monkeypatch):
 monkeypatch.setattr(c.universe,"symbols",lambda:("HYPEUSDT",))
 x=c.run(snapshot={"decisions":{}},kline_loader=lambda s: (_ for _ in ()).throw(RuntimeError("provider 451")),output=tmp_path/"l")
 assert x["captured_n"]==0 and x["failed_n"]==1
 assert "451" in x["failed"][0]["reason"]
