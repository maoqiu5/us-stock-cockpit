from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from .models import GoldManualTrade, GoldMonitor


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
GOLD_QUOTE_CACHE_PATH = Path(os.environ.get("GOLD_QUOTE_CACHE_PATH", "data/usstock/market_cache/gold_quote.json"))


def gold_monitor_snapshot(manual_trades: list[GoldManualTrade] | None = None) -> GoldMonitor:
    quote = _minsheng_accumulated_gold_quote()
    is_trading_session = quote["status"] == "交易中" or _is_bank_gold_trading_session()
    position = _gold_position_summary(manual_trades or [], quote["price"])
    first_order_amount = _first_order_amount(quote["price"], quote["pct_change"], position["remaining_capital"], position["holding_grams"])
    reserve_cash = round(position["remaining_capital"] - first_order_amount, 2)
    action, confidence, advice, watch_points = _gold_advice(
        price=quote["price"],
        pct_change=quote["pct_change"],
        day_high=quote["day_high"],
        day_low=quote["day_low"],
        position=position,
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
        remaining_capital=position["remaining_capital"],
        holding_grams=position["holding_grams"],
        holding_cost=position["holding_cost"],
        holding_market_value=position["holding_market_value"],
        holding_pnl=position["holding_pnl"],
        holding_pnl_pct=position["holding_pnl_pct"],
        average_cost=position["average_cost"],
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
    # 民生/浙商/工银积存金暂无个人开放 API；先用建行主动积存公开分时价作为银行积存金实盘参考锚。
    is_trading_session = _is_bank_gold_trading_session()
    if not is_trading_session:
        cached_quote = _load_cached_gold_quote()
        if cached_quote:
            return _quote_with_session_status(cached_quote, is_trading_session, "休市，显示最后报价")

    for quote_loader in (_ccb_accumulated_gold_quote, _akshare_sge_gold_quote, _sina_sge_gold_quote):
        try:
            quote = _quote_with_session_status(quote_loader(), is_trading_session)
            _save_cached_gold_quote(quote)
            return quote
        except Exception:
            continue
    cached_quote = _load_cached_gold_quote()
    if cached_quote:
        return _quote_with_session_status(cached_quote, is_trading_session, "接口暂不可用，显示最后报价")
    return {
        "price": SCREENSHOT_PRICE,
        "change": SCREENSHOT_CHANGE,
        "pct_change": SCREENSHOT_PCT_CHANGE,
        "day_high": SCREENSHOT_DAY_HIGH,
        "day_low": SCREENSHOT_DAY_LOW,
        "reference_price": SCREENSHOT_REFERENCE,
        "symbol": "CMBC_BANK_GOLD",
        "reference_name": "民生银行黄金截图基准",
        "status": "交易中" if is_trading_session else "休市，暂无缓存，显示截图基准",
        "time": _now_label(),
        "trend_points": [],
        "source": "民生银行截图基准 / 尚未形成真实报价缓存",
    }


def _intraday_trend_points(quote: dict) -> list[dict[str, float | str]]:
    if quote.get("trend_points"):
        return quote["trend_points"]
    return []


def _ccb_accumulated_gold_quote() -> dict:
    response = httpx.get(
        "https://gold1.ccb.com/webtran/static/trendchart/getAccountData.gsp",
        params={"dateType": "timeSharing", "sec_code": "999933"},
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": "https://gold1.ccb.com/chn/home/gold_new/hqzs/index.shtml",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=5,
        trust_env=False,
    )
    response.raise_for_status()
    payload = json.loads(response.text.strip())
    points = json.loads(payload["realTimePrice"])
    if not points:
        raise ValueError("CCB accumulated gold returned no trend points")
    last_price = float(payload["new_pri"])
    previous_close = float(payload["lastclo_quo"])
    pct_change = float(payload["price_chg"])
    return {
        "price": last_price,
        "change": round(last_price - previous_close, 2),
        "pct_change": pct_change,
        "day_high": float(payload["hig_pri"]),
        "day_low": float(payload["low_pri"]),
        "reference_price": previous_close,
        "symbol": "CCB_999933",
        "reference_name": "建设银行主动积存价 / 银行积存金真实分时参考",
        "status": "交易中" if _is_bank_gold_trading_session() else "非交易时段",
        "time": _ccb_time_label(str(payload["time"])),
        "trend_points": _trend_points_from_ccb_rows(points),
        "source": f"建设银行黄金积存报价 999933 · 本地刷新 {_now_label()}",
    }


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
        "trend_points": [{"time": quote_time.split(" ", 1)[-1], "price": price}],
        "source": f"新浪财经/上海黄金交易所 Au99.99 · 本地刷新 {_now_label()}",
    }


def _load_cached_gold_quote() -> dict | None:
    try:
        if not GOLD_QUOTE_CACHE_PATH.exists():
            return None
        payload = json.loads(GOLD_QUOTE_CACHE_PATH.read_text(encoding="utf-8"))
        if not payload.get("price") or not payload.get("time"):
            return None
        return payload
    except Exception:
        return None


def _save_cached_gold_quote(quote: dict) -> None:
    try:
        GOLD_QUOTE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **quote,
            "cached_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        }
        GOLD_QUOTE_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return


def _quote_with_session_status(quote: dict, is_trading_session: bool, detail: str | None = None) -> dict:
    result = dict(quote)
    if is_trading_session:
        result["status"] = "交易中"
        return result

    cached_at = result.get("cached_at", "")
    detail_text = detail or "休市，显示最后报价"
    result["status"] = detail_text
    source_suffix = f" · {detail_text}"
    if cached_at:
        source_suffix += f" · 缓存 {cached_at}"
    source = str(result.get("source", "黄金报价缓存"))
    if detail_text not in source:
        result["source"] = f"{source}{source_suffix}"
    return result


def _trend_points_from_ccb_rows(rows: list[dict]) -> list[dict[str, float | str]]:
    points: list[dict[str, float | str]] = []
    last_index = len(rows) - 1
    for index, row in enumerate(rows):
        if index % 5 != 0 and index != last_index:
            continue
        raw_time = str(row["time"])
        label = _ccb_point_time_label(raw_time)
        points.append({"time": label, "price": round(float(row["new_pri"]), 2)})
    return points


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


def _ccb_time_label(raw_time: str) -> str:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2}:\d{2})", raw_time)
    if match:
        _, month, day, time_value = match.groups()
        return f"{month}/{day} {time_value}"
    return _now_label()


def _ccb_point_time_label(raw_time: str) -> str:
    parts = raw_time.split(",")
    if len(parts) >= 6:
        return f"{int(parts[3]):02d}:{int(parts[4]):02d}:{int(parts[5]):02d}"
    return raw_time


def _is_bank_gold_trading_session(now: datetime | None = None) -> bool:
    current = (now or datetime.now()).astimezone(ZoneInfo("Asia/Shanghai"))
    weekday = current.weekday()
    minutes = current.hour * 60 + current.minute
    if weekday == 6:
        return False
    if weekday == 0:
        return minutes >= 9 * 60 + 10
    if weekday == 5:
        return minutes < 2 * 60 + 30
    return True


def _gold_position_summary(trades: list[GoldManualTrade], live_price: float) -> dict[str, float]:
    holding_grams = 0.0
    holding_cost = 0.0
    for trade in trades:
        multiplier = 1 if trade.side.value == "BUY" else -1
        holding_grams += multiplier * trade.grams
        holding_cost += multiplier * trade.amount_cny
    holding_grams = round(max(holding_grams, 0), 4)
    holding_cost = round(max(holding_cost, 0), 2)
    holding_market_value = round(holding_grams * live_price, 2)
    holding_pnl = round(holding_market_value - holding_cost, 2)
    average_cost = round(holding_cost / holding_grams, 2) if holding_grams else 0.0
    holding_pnl_pct = round(holding_pnl / holding_cost * 100, 2) if holding_cost else 0.0
    remaining_capital = round(max(PLANNED_CAPITAL - holding_cost, 0), 2)
    return {
        "remaining_capital": remaining_capital,
        "holding_grams": holding_grams,
        "holding_cost": holding_cost,
        "holding_market_value": holding_market_value,
        "holding_pnl": holding_pnl,
        "holding_pnl_pct": holding_pnl_pct,
        "average_cost": average_cost,
    }


def _first_order_amount(price: float, pct_change: float, remaining_capital: float, holding_grams: float) -> float:
    if remaining_capital < MIN_PURCHASE_AMOUNT:
        return 0.0
    if holding_grams > 0 and remaining_capital < PLANNED_CAPITAL * 0.25:
        return 0.0
    if pct_change <= -0.8:
        amount = 4000
    elif pct_change <= -0.3:
        amount = 3000
    else:
        amount = 2000
    return float(max(MIN_PURCHASE_AMOUNT, min(amount, remaining_capital)))


def _gold_advice(price: float, pct_change: float, day_high: float, day_low: float, position: dict[str, float]):
    intraday_position = (price - day_low) / max(day_high - day_low, 0.01)
    if position["holding_grams"] > 0:
        if position["holding_pnl_pct"] <= -3:
            return (
                "暂停加仓",
                0.78,
                "当前黄金持仓已经出现明显浮亏，先不要机械补仓；等价格重新站回成本均价附近或出现更低风险的分批信号。",
                [
                    f"当前浮亏 {position['holding_pnl_pct']:.2f}%",
                    f"成本均价 ¥{position['average_cost']:.2f}/克",
                    "新增买入前先确认剩余资金和最大可承受回撤",
                ],
            )
        if price >= position["average_cost"] * 1.025:
            return (
                "持有观察",
                0.70,
                "当前价格高于成本均价，已有安全垫；不追高加仓，优先观察是否继续走强。",
                [
                    f"持仓收益 {position['holding_pnl_pct']:+.2f}%",
                    "若短线急涨，记录止盈观察价",
                    "剩余资金继续保留等待回落",
                ],
            )
        if pct_change <= -0.4 and intraday_position < 0.4 and position["remaining_capital"] >= MIN_PURCHASE_AMOUNT:
            return (
                "小额补仓",
                0.66,
                "价格回落且仍有剩余资金，可以考虑小额补仓，但单笔不要超过剩余资金的三分之一。",
                [
                    f"剩余资金 ¥{position['remaining_capital']:.2f}",
                    f"当前低于成本 ¥{position['average_cost']:.2f}/克",
                    "补仓后继续保留现金，不一次性打满",
                ],
            )
        return (
            "持仓跟踪",
            0.64,
            "当前已有黄金仓位，先根据成本均价、剩余资金和日内位置做动态观察，不需要频繁操作。",
            [
                f"持仓 {position['holding_grams']:.4f} 克",
                f"持仓收益 {position['holding_pnl']:+.2f} 元",
                "下一笔操作必须先记录成交价和克数",
            ],
        )
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
