"""Build real market-context inputs for the shadow reasoning challenger.

Consumes existing ATLAS candle/HTF evidence. No Production mutation.
"""
from __future__ import annotations
from market_context_reasoning import build as reason

def _ret(closes, bars):
    if len(closes)<=bars or not closes[-1-bars]: return None
    return round((closes[-1]/closes[-1-bars]-1)*100,3)

def _rsi(closes, period=14):
    if len(closes)<=period: return None
    gains=[]; losses=[]
    for a,b in zip(closes[-period-1:-1],closes[-period:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/period; al=sum(losses)/period
    if al==0: return 100.0
    return round(100-(100/(1+ag/al)),2)

def from_4h_klines(klines, *, trend_direction, htf_alignment, event_risk="UNKNOWN", catalyst_bias="UNKNOWN"):
    closes=[float(x["close"]) for x in klines if x.get("close") is not None]
    if len(closes)<43:
        return reason({"trend_direction":trend_direction,"htf_alignment":htf_alignment,
                       "event_risk":event_risk,"catalyst_bias":catalyst_bias})
    recent_high=max(closes[-42:])
    context={
      "trend_direction":trend_direction,
      "htf_alignment":htf_alignment,
      "return_7d_pct":_ret(closes,42),
      "return_30d_pct":_ret(closes,180) if len(closes)>180 else None,
      "rsi":_rsi(closes),
      "distance_from_recent_high_pct":round((closes[-1]/recent_high-1)*100,3) if recent_high else None,
      "event_risk":event_risk,
      "catalyst_bias":catalyst_bias,
    }
    out=reason(context); out["context"]=context; out["context_source"]="ATLAS_4H_KLINES"
    return out
