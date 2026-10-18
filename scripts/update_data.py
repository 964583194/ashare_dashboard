# -*- coding: utf-8 -*-
"""Best-effort public data updater. Missing or unreliable data is never fabricated."""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "dashboard.json")
NOW = datetime.now(ZoneInfo("Asia/Shanghai"))
try:
    with open(OUT, encoding="utf-8") as source_file:
        PREVIOUS = json.load(source_file)
except (OSError, ValueError):
    PREVIOUS = {}

D = {
    "meta": {"generated_at": NOW.strftime("%Y-%m-%d %H:%M:%S %Z"), "data_date": None, "overall_status": "部分数据接入中"},
    "overview": {"hs300": None, "chinext": None, "star50": None, "advancers": None, "decliners": None},
    "indices": [], "industry_flows": [], "concept_flows": [], "focus_sectors": [],
    "breadth": {"advancers": None, "decliners": None, "unchanged": None, "advance_decline_ratio": None},
    "valuation": {"hs300_pe": None, "hs300_pe_percentile": None, "equity_bond_spread": None, "cn10y_yield": None},
    "sources": [],
}

# Preserve last valid values for modules that fail during this run.
for section in ("overview", "breadth", "valuation"):
    if isinstance(PREVIOUS.get(section), dict):
        for key in D[section]:
            D[section][key] = PREVIOUS[section].get(key)
for section in ("indices", "industry_flows", "concept_flows", "focus_sectors"):
    if isinstance(PREVIOUS.get(section), list):
        D[section] = PREVIOUS[section]
D["meta"]["data_date"] = PREVIOUS.get("meta", {}).get("data_date")


def add_status(module, state, data_date=None, note="", records=0):
    D["sources"].append({"module": module, "status": state, "date": data_date, "note": note, "records": records})


def previous_status(module):
    entries = PREVIOUS.get("sources", []) if isinstance(PREVIOUS.get("sources", []), list) else []
    for item in entries:
        if isinstance(item, dict) and item.get("module") == module:
            return item
    return None


def fnum(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def rnd(value):
    value = fnum(value)
    return round(value, 2) if value is not None else None


index_map = [("沪深300", "sh000300", "hs300"), ("创业板指", "sz399006", "chinext"),
             ("科创50", "sh000688", "star50"), ("上证指数", "sh000001", None),
             ("深证成指", "sz399001", None)]
try:
    import akshare as ak
except Exception as exc:
    ak = None
    add_status("指数行情", "失败，保留旧数据", D["meta"]["data_date"],
               f"AkShare初始化失败：{type(exc).__name__}: {str(exc)[:120]}", len(D["indices"]))

if ak is not None:
    for name, symbol, key in index_map:
        try:
            frame = ak.stock_zh_index_daily_em(symbol=symbol)
            if frame is None or frame.empty:
                raise ValueError("接口返回空数据")
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            if "close" not in frame.columns:
                raise ValueError("缺少收盘价字段")
            last = float(frame.iloc[-1]["close"])
            data_date = frame.iloc[-1]["date"].strftime("%Y-%m-%d")

            def return_pct(period):
                if len(frame) <= period:
                    return None
                prior = fnum(frame.iloc[-(period + 1)]["close"])
                return round((last / prior - 1) * 100, 2) if prior not in (None, 0) else None

            item = {"name": name, "latest": rnd(last), "change_pct": return_pct(1),
                    "change_5d": return_pct(5), "change_20d": return_pct(20), "date": data_date}
            D["indices"] = [row for row in D["indices"] if row.get("name") != name] + [item]
            if key:
                D["overview"][key] = rnd(last)
            dates = [row.get("date") for row in D["indices"] if row.get("date")]
            D["meta"]["data_date"] = max(dates) if dates else data_date
            add_status(name, "成功", data_date, "AkShare/Eastmoney公开指数日线；涨跌幅由收盘价计算", 1)
        except Exception as exc:
            old = next((row for row in D["indices"] if row.get("name") == name), None)
            add_status(name, "更新失败，保留旧数据" if old else "失败", old.get("date") if old else None,
                       f"{type(exc).__name__}: {str(exc)[:120]}", 1 if old else 0)


def sector_flow(sector_type):
    frame = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)
    if frame is None or frame.empty:
        return []
    columns = list(frame.columns)

    def find(*words):
        return next((column for column in columns if any(word in str(column) for word in words)), None)

    name_col = find("名称", "板块")
    change_col = find("涨跌幅")
    inflow_col = find("主力净流入", "净流入")
    ratio_col = find("主力净流入占比", "净流入占比")
    result = []
    for _, row in frame.head(20).iterrows():
        inflow = fnum(row.get(inflow_col)) if inflow_col else None
        if inflow is not None:
            inflow /= 1e8  # Eastmoney rank reports yuan; display 亿元.
        name = row.get(name_col) if name_col else None
        result.append({"name": str(name) if name is not None else "未知板块",
                       "change_pct": rnd(row.get(change_col)) if change_col else None,
                       "main_net_inflow": rnd(inflow),
                       "inflow_ratio": rnd(row.get(ratio_col)) if ratio_col else None})
    return sorted(result, key=lambda row: row["main_net_inflow"] if row["main_net_inflow"] is not None else -1e30, reverse=True)


if ak is not None:
    for label, sector_type, section in (("行业板块资金", "行业资金流", "industry_flows"),
                                       ("概念板块资金", "概念资金流", "concept_flows")):
        try:
            result = sector_flow(sector_type)
            if result:
                D[section] = result
            state = "成功" if result else ("失败，保留旧数据" if D[section] else "失败")
            add_status(label, state, D["meta"]["data_date"],
                       "东方财富公开资金流排名（供应商估算值，亿元）", len(result) or len(D[section]))
        except Exception as exc:
            add_status(label, "失败，保留旧数据" if D[section] else "失败", D["meta"]["data_date"],
                       f"{type(exc).__name__}: {str(exc)[:120]}", len(D[section]))

keywords = ["科创50", "半导体", "CPO", "光模块", "AI应用", "电网设备", "黄金", "有色金属", "稀土", "储能", "电池"]
flows = D["industry_flows"] + D["concept_flows"]
D["focus_sectors"] = []
for keyword in keywords:
    match = next((row for row in flows if keyword.lower() in row.get("name", "").lower()), None)
    D["focus_sectors"].append({"name": match["name"] if match else keyword,
                                "change_pct": match.get("change_pct") if match else None,
                                "change_5d": None, "change_20d": None,
                                "status": "仅有当日资金排名；多日趋势待接入" if match else "本次来源未提供可靠数据"})

for label, note in (("市场宽度", "均线比例需可靠的全市场个股历史行情；暂缓接入"),
                    ("估值与股债利差", "百分位网历史接口尚未验证；利差需统一PE与国债口径后接入")):
    old = previous_status(label)
    add_status(label, "待接入", old.get("date") if old else None, note)

usable = bool(D["indices"] or D["industry_flows"] or D["concept_flows"])
if usable:
    dates = [row.get("date") for row in D["indices"] if row.get("date")]
    if dates:
        D["meta"]["data_date"] = max(dates)
    D["meta"]["overall_status"] = "基础行情可用；市场宽度与股债指标待接入"
else:
    D["meta"]["generated_at"] = PREVIOUS.get("meta", {}).get("generated_at") or D["meta"]["generated_at"]
    D["meta"]["overall_status"] = "本次更新失败；保留上次有效数据"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as output_file:
    json.dump(D, output_file, ensure_ascii=False, indent=2)
print(f"Wrote {OUT}; data_date={D['meta']['data_date'] or '暂无'}")
for source in D["sources"]:
    print(f"{source['module']}: {source['status']}; records={source['records']}; latest={source['date'] or '暂无'}; {source['note']}")
