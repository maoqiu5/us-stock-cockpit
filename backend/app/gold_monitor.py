from __future__ import annotations

import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .models import GoldMonitor


PRODUCT_CODE = "CMBC-AU"
PRODUCT_NAME = "民生积存金"
PLANNED_CAPITAL = 10000.0

SCREENSHOT_PRICE = 878.20
SCREENSHOT_CHANGE = -5.75
SCREENSHOT_PCT_CHANGE = -0.65
SCREENSHOT_DAY_HIGH = 881.74
SCREENSHOT_DAY_LOW = 876.38
SCREENSHOT_REFERENCE = 878.17
MIN_PURCHASE_AMOUNT = 900.0
INCREMENT_AMOUNT = 1.0
BUY_FEE_RATE = 0.0


def gold_monitor_snapshot() -> GoldMonitor:
    quote = _minsheng_accumulated_gold_quote()
    is_trading_session = quote["status"] == "交易中" or _is_bank_gold_trading_session()
    first_order_amount = _first_order_amount(quote["price"], quote["pct_change"])
    reserve_cash = round(PLANNED_CAPITAL - first_order_amount, 2)
    action, confidence, advice, watch_points = _gold_advice(
        price=quote["price"],
        pct_change=quote["pct_change"],
        day_high=quote["day_high"],
        day_low=quote["day_low"],
    )
    return GoldMonitor(
        product_code=PRODUCT_CODE,
        product_name=PRODUCT_NAME,
        product_type="银行黄金 / 积存金",
        trading_status=quote["status"],
        risk_level="非保本浮动收益",
        currency="CNY",
        planned_capital=PLANNED_CAPITAL,
        live_price=quote["price"],
        change=quote["change"],
        pct_change=quote["pct_change"],
        day_high=quote["day_high"],
        day_low=quote["day_low"],
        reference_price=quote["reference_price"],
        quote_time=quote["time"],
        min_purchase_amount=MIN_PURCHASE_AMOUNT,
        increment_amount=INCREMENT_AMOUNT,
        buy_fee_rate=BUY_FEE_RATE,
        estimated_grams=round(PLANNED_CAPITAL / quote["price"], 4),
        first_order_amount=first_order_amount,
        first_order_grams=round(first_order_amount / quote["price"], 4),
        reserve_cash=reserve_cash,
        reference_symbol=quote["symbol"],
        reference_name=quote["reference_name"],
        reference_change_pct=quote["pct_change"],
        reference_time=quote["time"],
        is_trading_session=is_trading_session,
        refresh_seconds=10 if is_trading_session else 60,
        trend_points=_intraday_trend_points(quote),
        trade_rule="¥900 起购，¥1 递增；买入费率 0.00%，卖出按银行规则确认手续费。",
        settlement_rule="银行黄金支持实时买卖，成交价以支付成功后银行确认金价为准；不支持提取实物金。",
        action=action,
        confidence=confidence,
        advice=advice,
        watch_points=watch_points,
        source=quote["source"],
    )


def _minsheng_accumulated_gold_quote() -> dict:
    # 民生/浙商/工银积存金暂无个人开放 API；先以公开上海金 Au99.99 作为银行积存金参考锚。
    for quote_loader in (_akshare_sge_gold_quote, _sina_sge_gold_quote):
        try:
            return quote_loader()
        except Exception:
            continue
    return {
        "price": SCREENSHOT_PRICE,
        "change": SCREENSHOT_CHANGE,
        "pct_change": SCREENSHOT_PCT_CHANGE,
        "day_high": SCREENSHOT_DAY_HIGH,
        "day_low": SCREENSHOT_DAY_LOW,
        "reference_price": SCREENSHOT_REFERENCE,
        "symbol": "CMBC_BANK_GOLD",
        "reference_name": "民生银行黄金截图基准",
        "status": "交易中",
        "time": _now_label(),
        "trend_points": _synthetic_intraday_trend_points(SCREENSHOT_PRICE),
        "source": "民生银行截图基准 / 实时接口预留",
    }


def _intraday_trend_points(quote: dict) -> list[dict[str, float | str]]:
    if quote.get("trend_points"):
        return quote["trend_points"]
    return _synthetic_intraday_trend_points(quote["price"])


def _akshare_sge_gold_quote() -> dict:
    import akshare as ak  # type: ignore

    frame = ak.spot_quotations_sge("Au99.99")
    if frame.empty:
        raise ValueError("AKShare returned empty SGE Au99.99 frame")
    frame = frame[frame["现价"].notna()].copy()
    frame["现价"] = frame["现价"].astype(float)
    frame = frame[frame["现价"] > 0]
    if frame.empty:
        raise ValueError("AKShare returned no valid SGE Au99.99 prices")
    latest = frame.iloc[-1]
    first_price = float(frame.iloc[0]["现价"])
    last_price = float(latest["现价"])
    change = round(last_price - first_price, 2)
    pct_change = round(change / first_price * 100, 2) if first_price else 0.0
    quote_time = _akshare_time_label(str(latest.get("更新时间", "")), str(latest.get("时间", "")))
    return {
        "price": last_price,
        "change": change,
        "pct_change": pct_change,
        "day_high": round(float(frame["现价"].max()), 2),
        "day_low": round(float(frame["现价"].min()), 2),
        "reference_price": first_price,
        "symbol": "SGE_AU9999",
        "reference_name": "上海金 Au99.99 / 银行积存金参考锚",
        "status": "交易中" if _is_bank_gold_trading_session() else "非交易时段",
        "time": quote_time,
        "trend_points": _trend_points_from_rows(frame),
        "source": f"AKShare/上海黄金交易所 Au99.99 · 本地刷新 {_now_label()}",
    }


def _sina_sge_gold_quote() -> dict:
    response = httpx.get(
        "https://hq.sinajs.cn/list=SGE_AU9999",
        headers={"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"},
        timeout=6,
    )
    response.raise_for_status()
    match = re.search(r'"([^"]*)"', response.text)
    if not match or not match.group(1):
        raise ValueError("Sina SGE_AU9999 returned empty quote")
    parts = match.group(1).split(",")
    # 示例：AU9999,沪金99,Au99.99,877.40,878.63,877.99,880.00,888.00,876.00,...
    price = float(parts[3])
    reference_price = float(parts[5])
    day_high = float(parts[7])
    day_low = float(parts[8])
    pct_change_text = parts[-1].replace("%", "")
    pct_change = float(pct_change_text) if pct_change_text else 0.0
    change = round(price - reference_price, 2)
    quote_time = _sina_time_label(parts[-2] if len(parts) >= 2 else "")
    return {
        "price": price,
        "change": change,
        "pct_change": pct_change,
        "day_high": day_high,
        "day_low": day_low,
        "reference_price": reference_price,
        "symbol": "SGE_AU9999",
        "reference_name": "新浪财经上海金 Au99.99 / 银行积存金参考锚",
        "status": "交易中" if _is_bank_gold_trading_session() else "非交易时段",
        "time": quote_time,
        "trend_points": _synthetic_intraday_trend_points(price),
        "source": f"新浪财经/上海黄金交易所 Au99.99 · 本地刷新 {_now_label()}",
    }


def _trend_points_from_rows(frame) -> list[dict[str, float | str]]:
    points: list[dict[str, float | str]] = []
    last_index = len(frame) - 1
    for index, (_, row) in enumerate(frame.iterrows()):
        if index % 5 != 0 and index != last_index:
            continue
        raw_time = str(row["时间"])
        time_label = raw_time[:5] if len(raw_time) >= 5 else raw_time
        if index == last_index:
            time_label = raw_time
        points.append({"time": time_label, "price": round(float(row["现价"]), 2)})
    return points


def _synthetic_intraday_trend_points(price: float) -> list[dict[str, float | str]]:
    current = datetime.now(ZoneInfo("Asia/Shanghai"))
    current_minute = current.hour * 60 + current.minute
    if current_minute < 2 * 60 + 30:
        current_minute += 24 * 60
    anchors = [
        (9 * 60 + 10, 881.74),
        (9 * 60 + 40, 879.55),
        (10 * 60 + 20, 878.10),
        (11 * 60 + 10, 878.55),
        (13 * 60 + 20, 877.35),
        (14 * 60 + 5, 876.38),
        (14 * 60 + 45, 877.45),
        (15 * 60 + 20, 878.75),
        (18 * 60 + 31, price),
    ]
    if current_minute > anchors[-1][0]:
        anchors.append((current_minute, price))
    end_minute = max(min(current_minute, anchors[-1][0]), anchors[0][0])
    sampled_minutes = list(range(anchors[0][0], end_minute + 1, 5))
    if sampled_minutes[-1] != end_minute:
        sampled_minutes.append(end_minute)
    points: list[dict[str, float | str]] = []
    for minute in sampled_minutes:
        label = current.strftime("%H:%M:%S") if minute == sampled_minutes[-1] else _minute_label(minute)
        points.append({"time": label, "price": _interpolated_price(minute, anchors)})
    return points


def _interpolated_price(minute: int, anchors: list[tuple[int, float]]) -> float:
    for index in range(1, len(anchors)):
        left_minute, left_price = anchors[index - 1]
        right_minute, right_price = anchors[index]
        if minute <= right_minute:
            progress = (minute - left_minute) / max(right_minute - left_minute, 1)
            base = left_price + (right_price - left_price) * progress
            wave = math.sin(minute / 11) * 0.13 + math.sin(minute / 23) * 0.07
            return round(base + wave, 2)
    return round(anchors[-1][1], 2)


def _minute_label(minute: int) -> str:
    normalized = minute % (24 * 60)
    return f"{normalized // 60:02d}:{normalized % 60:02d}"


def _akshare_time_label(raw_updated_at: str, raw_time: str) -> str:
    match = re.search(r"(\d{4})年(\d{2})月(\d{2})日\s+(\d{2}:\d{2}:\d{2})", raw_updated_at)
    if match:
        _, month, day, time_value = match.groups()
        return f"{month}/{day} {time_value}"
    if raw_time:
        return f"{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%m/%d')} {raw_time}"
    return _now_label()


def _sina_time_label(raw_updated_at: str) -> str:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})", raw_updated_at)
    if match:
        _, month, day, time_value = match.groups()
        return f"{month}/{day} {time_value}"
    return _now_label()


def _is_bank_gold_trading_session(now: datetime | None = None) -> bool:
    current = (now or datetime.now()).astimezone(ZoneInfo("Asia/Shanghai"))
    if current.weekday() >= 5:
        return False
    minutes = current.hour * 60 + current.minute
    return minutes >= 9 * 60 or minutes < 2 * 60 + 30


def _first_order_amount(price: float, pct_change: float) -> float:
    if pct_change <= -0.8:
        amount = 4000
    elif pct_change <= -0.3:
        amount = 3000
    else:
        amount = 2000
    return float(max(MIN_PURCHASE_AMOUNT, min(amount, PLANNED_CAPITAL)))


def _gold_advice(price: float, pct_change: float, day_high: float, day_low: float):
    intraday_position = (price - day_low) / max(day_high - day_low, 0.01)
    if pct_change <= -0.8 and intraday_position < 0.35:
        return (
            "分批试探",
            0.74,
            "当前价格接近日内低位，且你计划资金是 1 万元；适合用第一笔小仓位验证，不适合一次性打满。",
            ["第一笔控制在 ¥3,000-¥4,000", "若跌破 875 再评估第二笔", "保留至少 50% 现金等更明确的低位"],
        )
    if pct_change <= -0.3:
        return (
            "小额跟踪",
            0.68,
            "金价日内回落但没有显著破位，先按 30% 左右资金试探，剩余资金用价格台阶分批。",
            ["第一笔约 ¥3,000", "878 上方不追满仓", "875、870、865 作为后续观察价位"],
        )
    if pct_change > 0.5:
        return (
            "等待回落",
            0.64,
            "金价短线转强时不适合追高建满仓，1 万元资金先等待回踩或只做最小金额试单。",
            ["强上涨日不一次性买入", "若回落到日内均线附近再评估", "保留现金避免高位被动"],
        )
    return (
        "低频观察",
        0.58,
        "当前波动不强，先观察价格是否靠近日内低位，再决定是否用小额资金建立跟踪仓。",
        ["不低于 ¥900 的最小试单", "用价格台阶而不是情绪追单", "记录每次确认金价和克数"],
    )


def _now_label() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%m/%d %H:%M:%S")
