import math
import profitability_true_path_ev as ev

def test_cost_adjusted_expected_r_is_locked():
 assert ev.ROUND_TRIP_COST_R==0.04
 assert abs(ev.net_expected_r(0.5)-0.46)<1e-12
 assert abs(ev.realized_net_r(1)-1.96)<1e-12
 assert abs(ev.realized_net_r(0)+1.04)<1e-12

def test_brier_and_log_loss_are_reported():
 m=ev.calibration([{"p":0.8,"y":1},{"p":0.2,"y":0}])
 assert m["n"]==2 and abs(m["brier"]-0.04)<1e-9
 assert m["log_loss"]>0

def test_purge_and_embargo_are_12h_and_non_overlapping():
 h=3600000;c=100*h
 rows=[{"t":87*h},{"t":88*h},{"t":100*h},{"t":112*h},{"t":113*h}]
 assert [x["t"] for x in ev.purged_fit(rows,c)]==[87*h,88*h]
 assert [x["t"] for x in ev.embargoed_exam(rows,c)]==[113*h]

def test_safety_contract():
 s=ev.safety()
 assert s["threshold"]==68
 assert s["production_impact"]=="NONE"
 assert s["can_override_final_gate"] is False
 assert s["automatic_promotion"] is False
 assert s["cost_locked"] is True
