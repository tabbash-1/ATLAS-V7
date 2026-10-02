import profitability_true_path_metrics as m
import profitability_true_path_forward_shadow as fs

def test_locked_cost_and_embargo_contract():
 s=m.safety();assert s["threshold"]==68;assert s["round_trip_cost_bps"]==30.0;assert s["purge_hours"]>=12;assert s["embargo_hours"]>=12;assert s["can_override_final_gate"] is False

def test_costs_reduce_both_win_and_loss_r():
 assert m.net_r(1,100,10)<2.0
 assert m.net_r(0,100,10)<-1.0

def test_probability_metrics_known_values():
 q=m.probability_metrics([{"p":.8,"y":1},{"p":.2,"y":0}]);assert q["n"]==2;assert abs(q["brier"]-.04)<1e-9;assert q["log_loss"]>0

def test_forward_shadow_is_pending_and_non_production():
 z=fs.candidate("BTCUSDT",1,"UP",100,90,120,.6,.5,"m","f");assert z["settlement"]=="PENDING";assert z["can_override_production"] is False;assert fs.safety()["strict_forward"] is True
