import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/"research"/"alpha_core_v2.py"
spec=importlib.util.spec_from_file_location("alpha_core_v2",P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def _ctx(**kw):
    base={
        "symbol":"BTCUSDT",
        "d1":"LONG","d4":"SHORT","d12":"LONG","d24":"LONG",
        "recent_4h_side":"SHORT","move4_atr":-0.8,"move12_atr":1.2,
        "atr14":1.0,"rsi14":44.0,"extension_atr":0.6,
        "volume_ratio":1.0,"efficiency12":0.55,
        "btc_d1":"LONG","btc_d4":"LONG","btc_d12":"LONG",
    }
    base.update(kw)
    return base


def test_safety_contract_is_shadow_only():
    assert m.VERSION=="ATLAS_ALPHA_CORE_V2_REGIME_ADAPTIVE"
    assert m.SAFETY["research_only"] is True
    assert m.SAFETY["production_effect"]=="NONE"
    assert m.SAFETY["can_override_production"] is False
    assert m.SAFETY["can_override_final_gate"] is False
    assert m.SAFETY["can_change_threshold"] is False
    assert m.SAFETY["can_create_trade"] is False
    assert m.SAFETY["live_execution"] is False


def test_pullback_uses_12h_thesis_only_after_1h_resumption():
    x=m.route_context(_ctx())
    assert x["regime"]=="PULLBACK"
    assert x["decision"]=="LONG"
    assert x["playbook"]=="12H_THESIS_4H_PULLBACK_RESUMPTION"

    y=m.route_context(_ctx(d1="SHORT"))
    assert y["decision"]=="WAIT"
    assert "1H_RESUMPTION_MISSING" in y["blockers"]


def test_btc_first_blocks_opposed_alt():
    x=m.route_context(_ctx(symbol="ETHUSDT",btc_d4="SHORT"))
    assert x["decision"]=="WAIT"
    assert "BTC_4H_OPPOSES" in x["blockers"]


def test_range_fades_meaningful_4h_move_only_with_confirmation():
    x=m.route_context(_ctx(
        d1="SHORT",d4=None,d12=None,d24=None,
        recent_4h_side="LONG",move4_atr=0.9,
        efficiency12=0.20,rsi14=62.0,extension_atr=0.4,
    ))
    assert x["regime"]=="RANGE"
    assert x["decision"]=="SHORT"
    assert x["playbook"]=="4H_RANGE_MEAN_REVERSION"

    y=m.route_context(_ctx(
        d1="LONG",d4=None,d12=None,d24=None,
        recent_4h_side="LONG",move4_atr=0.9,
        efficiency12=0.20,rsi14=62.0,extension_atr=0.4,
    ))
    assert y["decision"]=="WAIT"
    assert "1H_REVERSAL_CONFIRMATION_MISSING" in y["blockers"]


def test_breakout_does_not_chase_extension():
    x=m.route_context(_ctx(
        d1="LONG",d4="LONG",d12="LONG",d24="LONG",
        recent_4h_side="LONG",move4_atr=1.1,
        volume_ratio=1.2,extension_atr=1.8,efficiency12=0.7,
    ))
    assert x["regime"]=="BREAKOUT"
    assert x["decision"]=="WAIT"
    assert "BREAKOUT_OVEREXTENDED" in x["blockers"]


def test_evidence_distribution_is_explicitly_uncalibrated():
    routed=m.route_context(_ctx())
    p=m._evidence_distribution(_ctx(),routed)
    assert set(p)=={"LONG","SHORT","WAIT"}
    assert abs(sum(p.values())-1.0)<1e-5


def _candles(ts):
    return [{"t":t,"o":float(i+1),"h":float(i+2),"l":float(i),"c":float(i+1.5),"v":1.0}
            for i,t in enumerate(ts)]


def test_resample_closed_rejects_open_and_gapped_htf_bars():
    rows=_candles([i*m.HOUR_MS for i in range(12)])
    assert len(m.resample_closed(rows,4,4*m.HOUR_MS))==1
    assert len(m.resample_closed(rows,12,11*m.HOUR_MS))==0
    assert len(m.resample_closed(rows,12,12*m.HOUR_MS))==1

    gap=_candles([i*m.HOUR_MS for i in range(12) if i!=5])
    assert m.resample_closed(gap,12,12*m.HOUR_MS)==[]
