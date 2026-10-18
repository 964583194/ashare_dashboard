# -*- coding: utf-8 -*-
"""Best-effort public data updater. Missing/unreliable data stays null, never fabricated."""
import json, os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "dashboard.json")
NOW = datetime.now(ZoneInfo("Asia/Shanghai"))
D = {
 "meta":{"generated_at":NOW.strftime("%Y-%m-%d %H:%M:%S %Z"),"data_date":None,"overall_status":"部分数据接入中"},
 "overview":{"hs300":None,"chinext":None,"star50":None,"advancers":None,"decliners":None},
 "indices":[],"industry_flows":[],"concept_flows":[],"focus_sectors":[],
 "breadth":{"advancers":None,"decliners":None,"unchanged":None,"advance_decline_ratio":None},
 "valuation":{"hs300_pe":None,"hs300_pe_percentile":None,"equity_bond_spread":None,"cn10y_yield":None},
 "sources":[]
}
def add_status(module,state,date=None,note=""):
 D["sources"].append({"module":module,"status":state,"date":date,"note":note})
def fnum(v):
 try:
  if pd.isna(v): return None
  return float(v)
 except Exception: return None
def rnd(v):
 v=fnum(v)
 return round(v,2) if v is not None else None

# Index history through AkShare/Eastmoney public interface.
index_map=[("沪深300","sh000300","hs300"),("创业板指","sz399006","chinext"),("科创50","sh000688","star50"),("上证指数","sh000001",None),("深证成指","sz399001",None)]
try:
 import akshare as ak
 for name,symbol,key in index_map:
  try:
   df=ak.stock_zh_index_daily_em(symbol=symbol)
   if df is None or df.empty: raise ValueError("接口返回空数据")
   df=df.copy()
   df["date"]=pd.to_datetime(df["date"],errors="coerce")
   df=df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
   col="close" if "close" in df.columns else None
   if not col: raise ValueError("缺少收盘价字段")
   last=float(df.iloc[-1][col]); ds=df.iloc[-1]["date"].strftime("%Y-%m-%d")
   def ret(n):
    if len(df)<=n: return None
    prev=fnum(df.iloc[-(n+1)][col])
    return round((last/prev-1)*100,2) if prev not in (None,0) else None
   D["indices"].append({"name":name,"latest":rnd(last),"change_pct":ret(1),"change_5d":ret(5),"change_20d":ret(20),"date":ds})
   if key: D["overview"][key]=rnd(last)
   D["meta"]["data_date"]=max(filter(None,[D["meta"]["data_date"],ds]),default=ds)
   add_status(name,"成功",ds,"AkShare公开指数日线；收益率由收盘价计算")
  except Exception as e: add_status(name,"失败",None,f"{type(e).__name__}: {str(e)[:120]}")
except Exception as e:
 add_status("指数行情","失败",None,f"AkShare初始化失败：{type(e).__name__}: {str(e)[:120]}")

def sector_flow(sector_type):
 import akshare as ak
 df=ak.stock_sector_fund_flow_rank(indicator="今日",sector_type=sector_type)
 if df is None or df.empty: return []
 cols=list(df.columns)
 def find(*words):
  return next((c for c in cols if any(w in str(c) for w in words)),None)
 nc=find("名称","板块"); cc=find("涨跌幅"); ic=find("主力净流入","净流入"); rc=find("主力净流入占比","净流入占比")
 out=[]
 for _,row in df.head(20).iterrows():
  name=row.get(nc) if nc else None
  inflow=fnum(row.get(ic)) if ic else None
  # Public endpoint usually reports yuan; convert to 亿元 only when magnitude supports it.
  if inflow is not None and abs(inflow)>=1e7: inflow=inflow/1e8
  out.append({"name":str(name) if name is not None else "未知板块","change_pct":rnd(row.get(cc)) if cc else None,
              "main_net_inflow":rnd(inflow),"inflow_ratio":rnd(row.get(rc)) if rc else None})
 out.sort(key=lambda x: x["main_net_inflow"] if x["main_net_inflow"] is not None else -1e30,reverse=True)
 return out

for label,typ,key in [("行业板块资金","行业资金流","industry_flows"),("概念板块资金","概念资金流","concept_flows")]:
 try:
  D[key]=sector_flow(typ)
  add_status(label,"成功" if D[key] else "失败",D["meta"]["data_date"],"东方财富公开资金流向排名；资金流为供应商估算值")
 except Exception as e: add_status(label,"失败",None,f"{type(e).__name__}: {str(e)[:120]}")

keywords=["半导体","CPO","光模块","AI应用","电网设备","黄金","有色金属","稀土","储能","电池"]
flows=D["industry_flows"]+D["concept_flows"]
for kw in keywords:
 match=next((x for x in flows if kw.lower() in x.get("name","").lower()),None)
 D["focus_sectors"].append({"name":match["name"] if match else kw,
  "change_pct":match.get("change_pct") if match else None,"change_5d":None,"change_20d":None,
  "status":"仅当日数据；多日趋势待接入" if match else "本次资金排名未匹配到该板块"})

# Intentionally do not fabricate breadth, valuation percentiles, or bond spreads.
add_status("市场宽度","待接入",None,"需要验证全市场涨跌家数的稳定来源")
add_status("估值与股债利差","待接入",None,"历史分位/利差需稳定历史序列与口径核验后再接入")
if D["indices"] and (D["industry_flows"] or D["concept_flows"]):
 D["meta"]["overall_status"]="基础行情已更新；其他指标分步接入"
elif D["indices"]:
 D["meta"]["overall_status"]="指数行情部分可用；板块资金源待排查"
else:
 D["meta"]["overall_status"]="本次更新失败或数据源不可用"

os.makedirs(os.path.dirname(OUT),exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f: json.dump(D,f,ensure_ascii=False,indent=2)
print("Wrote",OUT)
print("Data date:",D["meta"]["data_date"])
print("Indices:",len(D["indices"]),"Industry flows:",len(D["industry_flows"]),"Concept flows:",len(D["concept_flows"]))
