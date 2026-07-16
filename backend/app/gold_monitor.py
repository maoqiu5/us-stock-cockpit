from __future__ import annotations

from datetime import datetime

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
        reference_symbol="CMBC_BANK_GOLD",
        reference_name="民生银行黄金实时买卖价",
        reference_change_pct=quote["pct_change"],
        reference_time=quote["time"],
        trade_rule="¥900 起购，¥1 递增；买入费率 0.00%，卖出按银行规则确认手续费。",
        settlement_rule="银行黄金支持实时买卖，成交价以支付成功后银行确认金价为准；不支持提取实物金。",
        action=action,
        confidence=confidence,
        advice=advice,
        watch_points=watch_points,
        source=quote["source"],
    )


def _minsheng_accumulated_gold_quote() -> dict:
    # 民生银行 App 内报价暂未接入开放 API；第一版以截图价作为本地基准，后续可替换为抓包/官方接口适配器。
    return {
        "price": SCREENSHOT_PRICE,
        "change": SCREENSHOT_CHANGE,
        "pct_change": SCREENSHOT_PCT_CHANGE,
        "day_high": SCREENSHOT_DAY_HIGH,
        "day_low": SCREENSHOT_DAY_LOW,
        "reference_price": SCREENSHOT_REFERENCE,
        "status": "交易中",
        "time": _now_label(),
        "source": "民生银行截图基准 / 实时接口预留",
    }


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
    return datetime.now().strftime("%m/%d %H:%M")
