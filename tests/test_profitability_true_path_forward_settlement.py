import profitability_true_path_forward_settlement as s

def c(t,h,l):return {"t":t,"h":h,"l":l,"o":100,"c":100,"v":1}
def test_pending_before_12h():
 z={"settlement":"PENDING","decision_t":0,"symbol":"BTCUSDT","side":"UP","entry":100,"stop":85}
 assert s.settle_row(z,11*s.H,lambda *a:[])["settlement"]=="PENDING"
def test_settles_win_cost_aware_after_12h():
 z={"settlement":"PENDING","decision_t":0,"symbol":"BTCUSDT","side":"UP","entry":100,"stop":85}
 fut=[c(i*s.H,131 if i==12 else 110,99) for i in range(1,13)]
 q=s.settle_row(z,13*s.H,lambda *a:fut);assert q["settlement"]=="WIN";assert q["net_r"]<2.0
def test_same_candle_tp_sl_is_loss():
 z={"settlement":"PENDING","decision_t":0,"symbol":"BTCUSDT","side":"UP","entry":100,"stop":85}
 fut=[c(i*s.H,131 if i==1 else 110,84 if i==1 else 99) for i in range(1,13)]
 q=s.settle_row(z,13*s.H,lambda *a:fut);assert q["settlement"]=="LOSS";assert q["net_r"]<-1.0
