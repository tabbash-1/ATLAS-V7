#!/usr/bin/env python3
"""ADP V6 reversal-confirmation development. Older year only; recent year sealed."""
from __future__ import annotations
import argparse,json,statistics,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from historical_core_4_12h_replay import fetch_1h,ema
SYMBOLS=["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","ZECUSDT","ADAUSDT","LINKUSDT","AVAXUSDT","LTCUSDT"]
COST=.10
def pct(a,b):return 100*(b/a-1) if a else 0
def bias(h):
 c=[x["c"] for x in h];e20=ema(c[-80:],20);e50=ema(c[-80:],50);vs=[x["v"] for x in h[-25:-1]]
 rv=h[-1]["v"]/statistics.mean(vs) if vs and statistics.mean(vs)>0 else 0
 return c[-1]<e20<e50 and pct(c[-9],c[-1])<0 and rv>=1
def confirm(d,j,kind):
 c=d[j]
 if kind=="green": return c["c"]>c["o"]
 if kind=="prev_high": return j>0 and c["c"]>d[j-1]["h"]
 if kind=="two_green": return j>1 and c["c"]>c["o"] and d[j-1]["c"]>d[j-1]["o"]
 if kind=="ema5": return j>=6 and c["c"]>ema([x["c"] for x in d[j-6:j+1]],5)
 if kind=="mom2": return j>=2 and c["c"]>d[j-2]["c"]
 return False
def trades(d,cut,kind,wait,hold):
 out=[];i=120;next_allowed=-1
 while i<len(d)-hold-1 and d[i]["t"]<cut:
  if i<next_allowed:i+=1;continue
  if bias(d[:i+1]):
   ent=None
   for j in range(i+1,min(i+wait+1,len(d)-hold)):
    if d[j]["t"]>=cut:break
    if confirm(d,j,kind):ent=j;break
   if ent is not None:
    ret=pct(d[ent]["c"],d[ent+hold]["c"])-COST
    out.append(ret);next_allowed=ent+hold;i=next_allowed;continue
  i+=1
 return out
def st(v):
 gp=sum(x for x in v if x>0);gl=abs(sum(x for x in v if x<=0))
 return {"n":len(v),"win_rate_pct":round(100*sum(x>0 for x in v)/len(v),2) if v else None,"avg_net_pct":round(statistics.mean(v),4) if v else None,
 "median_net_pct":round(statistics.median(v),4) if v else None,"profit_factor":round(gp/gl,4) if gl else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--days",type=int,default=730);ap.add_argument("--end-ms",type=int);a=ap.parse_args()
 end=a.end_ms or (int(time.time()*1000)//3600000)*3600000;cut=end-365*24*3600*1000
 market={s:fetch_1h(s,a.days,end) for s in SYMBOLS};res={}
 configs=[(k,w,h) for k in ("green","prev_high","two_green","ema5","mom2") for w in (2,4,8) for h in (4,8,12)]
 for k,w,h in configs:
  vals=[];by={}
  for s,d in market.items():
   x=trades(d,cut,k,w,h);vals+=x;by[s]=st(x)
  res[f"{k}_wait{w}_hold{h}"]={"overall":st(vals),"by_symbol":by}
 eligible=[]
 for k,v in res.items():
  o=v["overall"]; positives=sum(1 for z in v["by_symbol"].values() if z["avg_net_pct"] is not None and z["avg_net_pct"]>0)
  if o["n"]>=500 and o["profit_factor"] is not None and positives>=7:eligible.append((k,v,positives))
 best=max(eligible,key=lambda x:(x[1]["overall"]["profit_factor"],x[1]["overall"]["avg_net_pct"])) if eligible else None
 out={"schema":"ADP_V6_REVERSAL_CONFIRMATION_DEV","research_only":True,"production_effect":"NONE","data_policy":"OLDER_YEAR_ONLY_RECENT_YEAR_SEALED",
 "cost_pct":COST,"candidate_count":len(configs),"eligibility":"n>=500 and >=7/11 symbols positive; rank by PF then avg net",
 "best":({best[0]:{**best[1],"positive_symbols":best[2]}} if best else None),"candidates":res}
 print("ADP_V6_DEV="+json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
