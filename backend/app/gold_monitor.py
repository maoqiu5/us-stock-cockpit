from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.request import Request, urlopen

from .models import GoldMonitor


FUND_CODE = "002611"
FUND_NAME = "博时黄金ETF联接C"
REFERENCE_ETF_SECID = "1.518880"

SCREENSHOT_VALUE = 10646.93
SCREENSHOT_YESTERDAY_PNL = -16.59
SCREENSHOT_HOLDING_PNL = -1853.07
SCREENSHOT_HOLDING_PNL_RATE = -14.82
SCREENSHOT_CUMULATIVE_PNL = 1230.07


def gold_monitor_snapshot() -> GoldMonitor:
    fund_quote = _fund_estimate_quote()
    reference = _gold_etf_reference()
    latest_nav = fund_quote["latest_nav"]
    estimated_nav = fund_quote["estimated_nav"]
    cost_basis = round(SCREENSHOT_VALUE - SCREENSHOT_HOLDING_PNL, 2)
    estimated_units = round(SCREENSHOT_VALUE / latest_nav, 2) if latest_nav else 0
    cost_nav = round(cost_basis / estimated_units, 4) if estimated_units else 0
    action, confidence, advice, watch_points = _gold_advice(
        holding_pnl_rate=SCREENSHOT_HOLDING_PNL_RATE,
        estimated_change_pct=fund_quote["estimated_change_pct"],
        reference_change_pct=reference["change_pct"],
    )
    return GoldMonitor(
        fund_code=FUND_CODE,
        fund_name=FUND_NAME,
        risk_level="中风险",
        currency="CNY",
        current_value=SCREENSHOT_VALUE,
        estimated_units=estimated_units,
        cost_basis=cost_basis,
        cost_nav=cost_nav,
        latest_nav=latest_nav,
        latest_nav_date=fund_quote["latest_nav_date"],
        estimated_nav=estimated_nav,
        estimated_change_pct=fund_quote["estimated_change_pct"],
        estimated_time=fund_quote["estimated_time"],
        yesterday_pnl=SCREENSHOT_YESTERDAY_PNL,
        holding_pnl=SCREENSHOT_HOLDING_PNL,
        holding_pnl_rate=SCREENSHOT_HOLDING_PNL_RATE,
        cumulative_pnl=SCREENSHOT_CUMULATIVE_PNL,
        reference_symbol="518880.SH",
        reference_name=reference["name"],
        reference_price=reference["price"],
        reference_change_pct=reference["change_pct"],
        reference_time=reference["time"],
        trade_rule="买入确认 T+1，赎回到账按基金平台规则执行",
        settlement_rule="当日买入不按盘中价格即时成交，以基金净值确认；盘中估值只用于盯盘，不用于追价。",
        action=action,
        confidence=confidence,
        advice=advice,
        watch_points=watch_points,
        source=f"{fund_quote['source']} / {reference['source']}",
    )


def _fund_estimate_quote() -> dict:
    url = f"https://fundgz.1234567.com.cn/js/{FUND_CODE}.js"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
        with urlopen(request, timeout=8) as response:
            text = response.read().decode("utf-8", "ignore")
        match = re.search(r"jsonpgz\((.*)\);?", text)
        if not match:
            raise ValueError("unexpected fund estimate response")
        payload = json.loads(match.group(1))
        return {
            "latest_nav": float(payload["dwjz"]),
            "latest_nav_date": str(payload["jzrq"]),
            "estimated_nav": float(payload["gsz"]),
            "estimated_change_pct": float(payload["gszzl"]),
            "estimated_time": str(payload["gztime"]),
            "source": "天天基金估值",
        }
    except Exception:
        return {
            "latest_nav": 2.7592,
            "latest_nav_date": "2026-07-15",
            "estimated_nav": 2.7571,
            "estimated_change_pct": -0.08,
            "estimated_time": "2026-07-16 15:30",
            "source": "截图兜底估值",
        }


def _gold_etf_reference() -> dict:
    url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.518880&fields=f43,f57,f58,f170"
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
        data = payload["data"]
        return {
            "name": str(data.get("f58") or "黄金ETF华安"),
            "price": round(float(data["f43"]) / 1000, 4),
            "change_pct": round(float(data.get("f170") or 0) / 100, 2),
            "time": _now_label(),
            "source": "东方财富黄金ETF参考",
        }
    except Exception:
        return {
            "name": "黄金ETF华安",
            "price": 8.363,
            "change_pct": -0.07,
            "time": "07/16 15:00",
            "source": "黄金ETF参考兜底",
        }


def _gold_advice(holding_pnl_rate: float, estimated_change_pct: float, reference_change_pct: float):
    if holding_pnl_rate <= -12 and estimated_change_pct < -0.3:
        return (
            "暂停加仓",
            0.76,
            "当前持有亏损较深，且基金估值与黄金ETF参考同时走弱；T+1 品种不适合盘中追补，先等净值企稳。",
            ["持有收益率低于 -12%，禁止一次性补仓", "估算净值跌幅超过 -0.30% 时只观察", "若连续 3 个交易日转正，再评估小额定投"],
        )
    if holding_pnl_rate <= -12:
        return (
            "持有观察",
            0.68,
            "亏损已超过观察线，但今日估值波动不大；保留仓位，下一笔只允许按定投或分批规则执行。",
            ["不做盘中追价", "单次补仓不超过黄金仓目标差额的 25%", "用收盘后净值复核，而不是只看估算"],
        )
    if estimated_change_pct > 0.4 and reference_change_pct > 0:
        return (
            "等待回落",
            0.62,
            "黄金短线转强，但基金 T+1 确认有滞后；已有仓位先享受反弹，不追高买入。",
            ["估值上行日不追买", "若仓位超过目标权重，反弹后考虑降集中度", "保留定投节奏"],
        )
    return (
        "按纪律定投",
        0.58,
        "未触发强风险或强趋势信号，可维持小额定投和收盘后复核。",
        ["按 T+1 确认", "用基金净值做最终记录", "黄金仓位与美股科技仓分开看风险"],
    )


def _now_label() -> str:
    return datetime.now().strftime("%m/%d %H:%M")
