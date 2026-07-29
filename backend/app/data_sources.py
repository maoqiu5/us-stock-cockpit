from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataSourceStatus, Holding, MarketQuote, WatchlistItem
from .historical_prices import _yahoo_intraday_quote, is_us_market_open, previous_close_quotes
from .market_cache import cached_daily_closes, latest_cached_quotes, save_quotes
from .seed import WATCHLIST


FALLBACK_PRICES = {
    "NOK.US": (11.23, 0.0, 0.0, 0),
    "SMR.US": (8.36, 0.0, 0.0, 0),
    "NOK": (11.25, -0.45, -3.85, 0),
    "IAU": (76.28, 0.01, 0.01, 0),
    "NVDA": (212.5, 0.0, 0.0, 0),
}

_FUNDAMENTAL_CACHE: dict[str, tuple[float, dict[str, float | str]]] = {}
_FUNDAMENTAL_CACHE_SECONDS = 15 * 60
TREND_OVERHEATED_PCT = 5
TREND_DIRECTION_PCT = 1


def data_source_statuses() -> list[DataSourceStatus]:
    return [
        DataSourceStatus(
            id="fmp",
            name="Financial Modeling Prep",
            purpose="美股股票池分钟级真实盘中行情",
            configured=bool(os.getenv("FMP_API_KEY")),
            status="active" if os.getenv("FMP_API_KEY") else "missing",
            detail="配置 FMP_API_KEY 后作为主行情源；使用 /stable/quote 批量读取股票池报价。",
        ),
        DataSourceStatus(
            id="akshare",
            name="AKShare",
            purpose="美股实时/准实时公开行情",
            configured=_module_available("akshare"),
            status="active" if _module_available("akshare") else "fallback",
            detail="FMP 不可用时使用 stock_us_spot_em；失败后切到 Yahoo intraday，最后才使用内置样例行情。",
        ),
        DataSourceStatus(
            id="yahoo-intraday",
            name="Yahoo Finance",
            purpose="美股盘中价格备用源",
            configured=True,
            status="active",
            detail="AKShare/Eastmoney 不可用时，逐个股票读取 Yahoo 1 分钟盘中图表数据。",
        ),
        DataSourceStatus(
            id="tushare",
            name="TuShare",
            purpose="美股日线、估值、财务和基本面",
            configured=bool(os.getenv("TUSHARE_TOKEN")),
            status="active" if os.getenv("TUSHARE_TOKEN") else "missing",
            detail="需要 TUSHARE_TOKEN；适合 PE/PEG/ROI 模型的日线和基本面，不作为实时价格主源。",
        ),
        DataSourceStatus(
            id="broker-import",
            name="ZA/uSMART 导入",
            purpose="个人券商持仓、成交和对账",
            configured=True,
            status="manual",
            detail="通过结单、CSV、截图 OCR 或手工记录导入；不需要券商 Open API。",
        ),
        DataSourceStatus(
            id="minsheng-gold",
            name="民生积存金",
            purpose="民生/浙商/工银积存金参考盯盘",
            configured=True,
            status="active",
            detail="优先使用建设银行主动积存公开分时价，备用 AKShare 上海金 Au99.99 与新浪 SGE_AU9999；民生/浙商/工行专属买卖价后续可接适配器。",
        ),
    ]


def market_quotes(symbols: Iterable[str] | None = None) -> list[MarketQuote]:
    tickers = [symbol.upper() for symbol in (symbols or FALLBACK_PRICES.keys())]
    if not is_us_market_open():
        quotes, _ = previous_close_quotes(tickers)
        return _save_and_fill_quotes(tickers, quotes)
    try:
        return _save_and_fill_quotes(tickers, _fmp_quotes(tickers))
    except Exception:
        pass
    try:
        return _save_and_fill_quotes(tickers, _akshare_quotes(tickers))
    except Exception:
        return _save_and_fill_quotes(tickers, _yahoo_quotes(tickers))


def _save_and_fill_quotes(tickers: list[str], quotes: list[MarketQuote]) -> list[MarketQuote]:
    quote_map = {quote.ticker: quote for quote in quotes}
    missing = [ticker for ticker in tickers if ticker not in quote_map]
    if missing:
        for cached in latest_cached_quotes(missing):
            quote_map.setdefault(cached.ticker, cached.model_copy(update={"source": f"{cached.source} · local-cache"}))
    output = [quote_map[ticker] for ticker in tickers if ticker in quote_map]
    save_quotes(output)
    return output


def dynamic_watchlist(items: list[WatchlistItem], holdings: list[Holding] | None = None, validation: dict[str, dict[str, float | str]] | None = None, quotes: dict[str, MarketQuote] | None = None) -> list[WatchlistItem]:
    tickers = [item.ticker for item in items]
    quotes = quotes or {quote.ticker: quote for quote in market_quotes(tickers)}
    holding_map = _holding_context(holdings or [])
    output: list[WatchlistItem] = []
    for item in items:
        quote = quotes.get(item.ticker)
        fundamentals = _fundamentals_for_ticker(item.ticker, quote.price if quote else None)
        output.append(_dynamic_watchlist_item(item, quote, fundamentals, holding_map.get(item.ticker), (validation or {}).get(item.ticker)))
    return output


def _dynamic_watchlist_item(item: WatchlistItem, quote: MarketQuote | None, fundamentals: dict[str, float | str], holding: dict[str, float] | None = None, validation: dict[str, float | str] | None = None) -> WatchlistItem:
    pct_change = quote.pct_change if quote else 0
    technicals = _historical_technicals(item.ticker, quote)
    trend = _trend_from_technicals(pct_change, technicals)
    data_status = _data_status(quote)
    tradable_quote = data_status in {"实时", "准实时"}
    fallback = _price_adjusted_fallback_metrics(item, quote)
    pe = _metric_value(fundamentals.get("pe"), fallback["pe"])
    peg = _metric_value(fundamentals.get("peg"), fallback["peg"])
    roi = _metric_value(fundamentals.get("roi"), item.roi)
    growth = _metric_value(fundamentals.get("growth"), item.growth)
    holding_pnl_pct = holding["pnl"] / holding["cost"] * 100 if holding and holding["cost"] > 0 else 0
    holding_weight = holding["value"] / holding["account_total"] * 100 if holding and holding["account_total"] > 0 else 0
    has_model_validation = validation is not None and validation.get("score") is not None
    model_score = int(_metric_value(validation.get("score") if has_model_validation else None, item.model_score))
    model_reason = str((validation or {}).get("reason") or item.model_reason or "尚未验证模型")
    model_pass = not has_model_validation or model_score >= 55
    watch = _watch_assessment(item, quote, trend, model_score, has_model_validation, holding_pnl_pct, holding_weight, data_status, technicals)
    eligible = pe <= 40 and peg <= 2 and roi >= 15 and growth >= 8 and trend in {"上行", "横盘"} and model_pass and tradable_quote and watch["score"] >= 58
    holding_risk = holding is not None and (holding_pnl_pct <= -15 or holding_weight >= 12)
    model_risk = has_model_validation and model_score < 40
    stale_risk = data_status in {"样例", "无行情"}
    signal = "RISK" if holding_risk or model_risk or stale_risk or trend == "过热" or pe > 45 or peg > 2.6 or pct_change < -5 else ("BUY" if eligible else "WATCH")
    signal_reason = _signal_reason(signal, pe, peg, roi, growth, trend, pct_change, holding_pnl_pct, holding_weight, holding is not None, model_score, model_reason, has_model_validation, data_status)
    lines = _price_discipline_lines(quote.price if quote else 0, signal, holding, holding_pnl_pct)
    return item.model_copy(update={
        "name": str(fundamentals.get("name") or item.name),
        "sector": str(fundamentals.get("sector") or item.sector),
        "pe": pe,
        "peg": peg,
        "roi": roi,
        "growth": growth,
        "trend": trend,
        "eligible": eligible,
        "signal": signal,
        "signal_reason": signal_reason,
        "model_score": model_score,
        "model_reason": model_reason,
        "watch_score": watch["score"],
        "watch_label": str(watch["label"]),
        "watch_reason": str(watch["reason"]),
        "entry_low_price": lines["entry_low"],
        "entry_high_price": lines["entry_high"],
        "chase_limit_price": lines["chase_limit"],
        "stop_loss_price": lines["stop_loss"],
        "take_profit_price": lines["take_profit"],
        "max_loss_amount": lines["max_loss"],
        "quote_source": quote.source if quote else "",
        "quote_updated_at": quote.updated_at if quote else "",
        "data_status": data_status,
        "volume_score": watch["volume_score"],
        "ma5": technicals["ma5"],
        "ma20": technicals["ma20"],
        "distance_to_20d_high_pct": technicals["distance_to_20d_high_pct"],
        "distance_to_20d_low_pct": technicals["distance_to_20d_low_pct"],
        "atr20": technicals["atr20"],
        "relative_volume": technicals["relative_volume"],
        "vwap_hint": technicals["vwap_hint"],
    })


def _holding_context(holdings: list[Holding]) -> dict[str, dict[str, float]]:
    account_total = sum(holding.market_value for holding in holdings)
    context: dict[str, dict[str, float]] = {}
    for holding in holdings:
        current = context.get(holding.ticker, {"cost": 0.0, "value": 0.0, "pnl": 0.0, "account_total": account_total})
        current["cost"] += holding.avg_cost * holding.qty
        current["value"] += holding.market_value
        current["pnl"] += holding.pnl
        context[holding.ticker] = current
    return context


def _signal_reason(signal: str, pe: float, peg: float, roi: float, growth: float, trend: str, pct_change: float, holding_pnl_pct: float, holding_weight: float, has_holding: bool, model_score: int, model_reason: str, has_model_validation: bool, data_status: str = "无行情") -> str:
    reasons: list[str] = []
    if data_status in {"缓存", "昨收", "样例", "无行情"}:
        reasons.append(f"行情状态 {data_status}，不生成立即买入")
    if has_holding and holding_pnl_pct <= -15:
        reasons.append(f"持仓亏损 {holding_pnl_pct:.2f}%")
    if has_holding and holding_weight >= 12:
        reasons.append(f"仓位 {holding_weight:.2f}% 超过 12%")
    if has_model_validation and model_score < 40:
        reasons.append(f"模型分 {model_score} 偏低")
    if pe > 45:
        reasons.append(f"PE {pe:.2f} > 45")
    if peg > 2.6:
        reasons.append(f"PEG {peg:.2f} > 2.6")
    if pct_change < -5:
        reasons.append(f"日内跌幅 {pct_change:.2f}%")
    if trend == "过热":
        reasons.append("日内涨幅 > 5%")
    if signal == "BUY" and not reasons:
        reasons.extend([
            f"PE {pe:.2f} <= 40",
            f"PEG {peg:.2f} <= 2",
            f"ROI {roi:.2f}% >= 15%",
            f"增长 {growth:.2f}% >= 8%",
            f"模型分 {model_score}" if has_model_validation else f"趋势 {trend}",
        ])
    if signal == "WATCH" and not reasons:
        reasons.append(f"未满足 BUY 全部条件；{model_reason}")
    return "；".join(reasons[:4])


def _data_status(quote: MarketQuote | None) -> str:
    if not quote:
        return "无行情"
    source = quote.source.lower()
    if "sample" in source:
        return "样例"
    if "local-cache" in source or "cache" in source:
        return "缓存"
    if "昨收" in quote.source or "previous" in source:
        return "昨收"
    return "实时" if quote.delay_seconds <= 60 else "准实时"


def _historical_technicals(ticker: str, quote: MarketQuote | None) -> dict[str, float]:
    blank = {
        "ma5": 0.0,
        "ma20": 0.0,
        "distance_to_20d_high_pct": 0.0,
        "distance_to_20d_low_pct": 0.0,
        "atr20": 0.0,
        "relative_volume": 0.0,
        "vwap_hint": 0.0,
    }
    price = quote.price if quote and quote.price > 0 else 0
    end = datetime.now().date()
    start = end - timedelta(days=45)
    rows = cached_daily_closes(ticker, start.isoformat(), end.isoformat())
    closes = [close for _, close in rows if close and close > 0]
    if price > 0:
        closes = closes + [price]
    if len(closes) < 5:
        return blank
    recent20 = closes[-20:]
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(recent20) / len(recent20) if recent20 else 0
    high20 = max(recent20) if recent20 else 0
    low20 = min(recent20) if recent20 else 0
    returns = [abs(closes[index] / closes[index - 1] - 1) for index in range(1, len(closes)) if closes[index - 1] > 0]
    recent_returns = returns[-20:]
    atr20 = (sum(recent_returns) / len(recent_returns) * price) if recent_returns and price > 0 else 0
    return {
        "ma5": round(ma5, 2),
        "ma20": round(ma20, 2),
        "distance_to_20d_high_pct": round((price / high20 - 1) * 100, 2) if price > 0 and high20 > 0 else 0.0,
        "distance_to_20d_low_pct": round((price / low20 - 1) * 100, 2) if price > 0 and low20 > 0 else 0.0,
        "atr20": round(atr20, 2),
        "relative_volume": 0.0,
        "vwap_hint": 0.0,
    }


def _trend_from_technicals(pct_change: float, technicals: dict[str, float]) -> str:
    ma5 = technicals.get("ma5", 0)
    ma20 = technicals.get("ma20", 0)
    distance_high = technicals.get("distance_to_20d_high_pct", 0)
    distance_low = technicals.get("distance_to_20d_low_pct", 0)
    if ma5 and ma20:
        if ma5 > ma20 * 1.01 and pct_change >= -1:
            return "上行"
        if ma5 < ma20 * 0.99 and pct_change <= 1:
            return "下行"
        if distance_high >= 0 and pct_change > TREND_OVERHEATED_PCT:
            return "过热"
        if distance_low and distance_low <= 3 and pct_change < 0:
            return "下行"
        return "横盘"
    return _trend_from_change(pct_change)


def _watch_assessment(item: WatchlistItem, quote: MarketQuote | None, trend: str, model_score: int, has_model_validation: bool, holding_pnl_pct: float, holding_weight: float, data_status: str, technicals: dict[str, float] | None = None) -> dict[str, int | str]:
    if not quote or quote.price <= 0:
        return {"score": 0, "label": "无行情", "reason": "缺少真实行情，暂不研判。", "volume_score": 0}
    technicals = technicals or {}
    volume_score = _volume_score(quote.volume, quote.price)
    score = 50
    if quote.pct_change >= 2:
        score += 14
    elif quote.pct_change >= 0.5:
        score += 7
    elif quote.pct_change <= -5:
        score -= 24
    elif quote.pct_change <= -2:
        score -= 12
    if trend == "过热":
        score -= 10
    elif trend == "上行":
        score += 8
    elif trend == "下行":
        score -= 10
    score += round((volume_score - 50) * 0.25)
    if has_model_validation:
        score += round((model_score - 55) * 0.35)
    ma5 = float(technicals.get("ma5") or 0)
    ma20 = float(technicals.get("ma20") or 0)
    distance_high = float(technicals.get("distance_to_20d_high_pct") or 0)
    distance_low = float(technicals.get("distance_to_20d_low_pct") or 0)
    if ma5 and ma20:
        if quote.price >= ma5 >= ma20:
            score += 10
        elif quote.price < ma20:
            score -= 10
        if distance_high >= -3:
            score += 5
        if 0 < distance_low <= 3:
            score -= 8
    if holding_pnl_pct <= -15:
        score -= 12
    if holding_weight >= 12:
        score -= 8
    if data_status in {"缓存", "昨收"}:
        score = min(score, 54)
    if data_status in {"样例", "无行情"}:
        score = min(score, 30)
    score = max(0, min(100, score))
    if data_status in {"缓存", "昨收"}:
        label = "缓存观察"
    elif data_status in {"样例", "无行情"}:
        label = "数据不足"
    elif quote.pct_change > 5:
        label = "过热冲高"
    elif quote.pct_change <= -5:
        label = "破位下行"
    elif score >= 72:
        label = "强势上行"
    elif score >= 58:
        label = "可跟踪加仓"
    elif score >= 42:
        label = "横盘等待"
    else:
        label = "弱势回避"
    reason_bits = [
        f"{data_status}行情 {quote.updated_at}",
        f"涨跌 {quote.pct_change:+.2f}%",
        f"成交确认 {volume_score}",
    ]
    if ma5 and ma20:
        reason_bits.append(f"MA5/20 {ma5:.2f}/{ma20:.2f}")
    if distance_high or distance_low:
        reason_bits.append(f"20日区间 高{distance_high:+.1f}% 低{distance_low:+.1f}%")
    if has_model_validation:
        reason_bits.append(f"模型分 {model_score}")
    if holding_pnl_pct:
        reason_bits.append(f"持仓盈亏 {holding_pnl_pct:+.1f}%")
    return {"score": score, "label": label, "reason": "；".join(reason_bits[:5]), "volume_score": volume_score}


def _volume_score(volume: float, price: float) -> int:
    dollar_volume = max(volume, 0) * max(price, 0)
    if dollar_volume >= 50_000_000:
        return 100
    if dollar_volume >= 15_000_000:
        return 82
    if dollar_volume >= 5_000_000:
        return 65
    if dollar_volume >= 1_000_000:
        return 48
    if dollar_volume > 0:
        return 30
    return 20


def _price_discipline_lines(price: float, signal: str, holding: dict[str, float] | None, holding_pnl_pct: float) -> dict[str, float]:
    if price <= 0:
        return {"entry_low": 0.0, "entry_high": 0.0, "chase_limit": 0.0, "stop_loss": 0.0, "take_profit": 0.0, "max_loss": 0.0}
    cost = float(holding["cost"]) / max(float(holding["value"]) / price, 0.0001) if holding and float(holding["value"]) > 0 else price
    if signal == "BUY":
        stop_loss = min(price * 0.92, price - max(price * 0.06, 0.08))
        take_profit = price * 1.15
        entry_low = price * 0.99
        entry_high = price * 1.005
        chase_limit = price * 1.025
    elif signal == "RISK":
        stop_loss = min(price * 0.95, cost * 0.85) if holding else price * 0.95
        take_profit = price * 1.08
        entry_low = 0.0
        entry_high = 0.0
        chase_limit = 0.0
    else:
        stop_loss = price * 0.90
        take_profit = price * 1.12
        entry_low = price * 0.985
        entry_high = price * 1.0
        chase_limit = price * 1.015
    account_total = float(holding["account_total"]) if holding else 0.0
    risk_budget = account_total * (0.003 if holding_pnl_pct < -10 else 0.005)
    return {
        "entry_low": round(entry_low, 2),
        "entry_high": round(entry_high, 2),
        "chase_limit": round(chase_limit, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "max_loss": round(risk_budget, 2),
    }


def _fundamentals_for_ticker(ticker: str, live_price: float | None) -> dict[str, float | str]:
    if _is_etf_like(ticker):
        return {}
    now = datetime.utcnow().timestamp()
    cache_key = _fmp_symbol(ticker)
    cached = _FUNDAMENTAL_CACHE.get(cache_key)
    if cached and now - cached[0] < _FUNDAMENTAL_CACHE_SECONDS:
        return _adjust_fundamentals_for_price(cached[1], live_price)
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return {}
    try:
        ratios = _fmp_json("ratios-ttm", cache_key, api_key)
        metrics = _fmp_json("key-metrics-ttm", cache_key, api_key)
        profile = _fmp_json("profile", cache_key, api_key)
        ratio = ratios[0] if isinstance(ratios, list) and ratios else {}
        metric = metrics[0] if isinstance(metrics, list) and metrics else {}
        company = profile[0] if isinstance(profile, list) and profile else {}
        pe = _float_or_none(ratio.get("priceToEarningsRatioTTM"))
        peg = _float_or_none(ratio.get("forwardPriceToEarningsGrowthRatioTTM")) or _float_or_none(ratio.get("priceToEarningsGrowthRatioTTM"))
        growth = pe / peg if pe and peg and peg > 0 else None
        raw = {
            "name": company.get("companyName") or company.get("symbol") or cache_key,
            "sector": company.get("sector") or company.get("industry") or "Fundamental",
            "price": _float_or_none(company.get("price")) or live_price or 0,
            "pe": pe,
            "peg": peg,
            "roi": (_float_or_none(metric.get("returnOnInvestedCapitalTTM")) or 0) * 100,
            "growth": growth,
        }
        _FUNDAMENTAL_CACHE[cache_key] = (now, raw)
        return _adjust_fundamentals_for_price(raw, live_price)
    except Exception:
        _FUNDAMENTAL_CACHE[cache_key] = (now, {})
        return {}


def _fmp_json(path: str, symbol: str, api_key: str):
    params = urlencode({"symbol": symbol, "apikey": api_key})
    request = Request(f"https://financialmodelingprep.com/stable/{path}?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def _adjust_fundamentals_for_price(fundamentals: dict[str, float | str], live_price: float | None) -> dict[str, float | str]:
    pe = _float_or_none(fundamentals.get("pe"))
    growth = _float_or_none(fundamentals.get("growth"))
    if not pe or not live_price:
        return fundamentals
    fmp_price = _float_or_none(fundamentals.get("price")) or live_price
    eps = fmp_price / pe if pe else None
    adjusted_pe = live_price / eps if eps else pe
    adjusted = dict(fundamentals)
    adjusted["pe"] = adjusted_pe
    adjusted["peg"] = adjusted_pe / growth if growth and growth > 0 else fundamentals.get("peg")
    return adjusted


def _fmp_quotes(tickers: list[str]) -> list[MarketQuote]:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise ValueError("FMP_API_KEY missing")
    quotes: list[MarketQuote] = []
    for ticker in tickers:
        try:
            quotes.extend(_fmp_quote_request([ticker], api_key))
        except Exception:
            try:
                quotes.append(_yahoo_intraday_quote(ticker))
            except Exception:
                quotes.append(_fallback_quote(ticker))
    return quotes


def _fmp_quote_request(tickers: list[str], api_key: str) -> list[MarketQuote]:
    symbols = [_fmp_symbol(ticker) for ticker in tickers]
    params = urlencode({"symbol": ",".join(symbols), "apikey": api_key})
    request = Request(f"https://financialmodelingprep.com/stable/quote?{params}", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if isinstance(payload, dict) and payload.get("Error Message"):
        raise ValueError(payload["Error Message"])
    if not isinstance(payload, list):
        raise ValueError("FMP returned unexpected quote payload")
    by_symbol = {str(item.get("symbol", "")).upper(): item for item in payload}
    return [_fmp_quote_for_ticker(ticker, by_symbol) for ticker in tickers]


def _fmp_quote_for_ticker(ticker: str, by_symbol: dict[str, dict]) -> MarketQuote:
    symbol = _fmp_symbol(ticker)
    item = by_symbol.get(symbol)
    if not item:
        raise ValueError(f"FMP returned no quote for {ticker}")
    price = float(item.get("price") or 0)
    if price <= 0:
        raise ValueError(f"FMP returned no price for {ticker}")
    return MarketQuote(
        ticker=ticker,
        name=item.get("name") or symbol,
        price=round(price, 4),
        change=round(float(item.get("change") or 0), 4),
        pct_change=round(float(item.get("changesPercentage") or item.get("changePercentage") or 0), 2),
        volume=float(item.get("volume") or 0),
        source="FMP quote",
        delay_seconds=60,
        updated_at=_fmp_time_label(item.get("timestamp")),
    )


def _yahoo_quotes(tickers: list[str]) -> list[MarketQuote]:
    quotes: list[MarketQuote] = []
    for ticker in tickers:
        try:
            quotes.append(_yahoo_intraday_quote(ticker))
        except Exception:
            quotes.append(_fallback_quote(ticker))
    return quotes


def _akshare_quotes(tickers: list[str]) -> list[MarketQuote]:
    import akshare as ak  # type: ignore

    frame = ak.stock_us_spot_em()
    code_col = _first_existing_column(frame.columns, ["代码", "symbol", "股票代码"])
    name_col = _first_existing_column(frame.columns, ["名称", "name", "股票名称"])
    price_col = _first_existing_column(frame.columns, ["最新价", "最新", "price"])
    change_col = _first_existing_column(frame.columns, ["涨跌额", "change"])
    pct_col = _first_existing_column(frame.columns, ["涨跌幅", "pct_chg", "change_percent"])
    volume_col = _first_existing_column(frame.columns, ["成交量", "volume"])
    quotes: list[MarketQuote] = []
    wanted = set(tickers)
    for _, row in frame.iterrows():
        raw_code = str(row[code_col]).upper()
        ticker = raw_code.split(".")[-1].replace("US", "")
        if ticker not in wanted:
            continue
        quotes.append(
            MarketQuote(
                ticker=next((wanted_ticker for wanted_ticker in wanted if wanted_ticker.replace(".US", "") == ticker), ticker),
                name=str(row.get(name_col, "")),
                price=float(row[price_col]),
                change=float(row.get(change_col, 0) or 0),
                pct_change=float(row.get(pct_col, 0) or 0),
                volume=float(row.get(volume_col, 0) or 0),
                source="AKShare/Eastmoney",
                delay_seconds=5,
                updated_at=_now_label(),
            )
        )
    if not quotes:
        raise ValueError("AKShare returned no requested symbols")
    return quotes


def _fallback_quote(ticker: str) -> MarketQuote:
    price, change, pct_change, volume = FALLBACK_PRICES.get(ticker, (100.0, 0.0, 0.0, 0.0))
    name = next((item.name for item in WATCHLIST if item.ticker == ticker), ticker)
    return MarketQuote(
        ticker=ticker,
        name=name,
        price=price,
        change=change,
        pct_change=pct_change,
        volume=volume,
        source="sample-fallback",
        delay_seconds=0,
        updated_at=_now_label(),
    )


def _first_existing_column(columns, candidates: list[str]):
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise KeyError(f"missing columns: {candidates}")


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _now_label() -> str:
    return datetime.utcnow().strftime("%m/%d %H:%M")


def _fmp_symbol(ticker: str) -> str:
    return ticker.upper().replace(".US", "")


def _fmp_time_label(timestamp) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%m/%d %H:%M")
    except Exception:
        return _now_label()


def _trend_from_change(pct_change: float) -> str:
    if pct_change > TREND_OVERHEATED_PCT:
        return "过热"
    if pct_change > TREND_DIRECTION_PCT:
        return "上行"
    if pct_change < -TREND_DIRECTION_PCT:
        return "下行"
    return "横盘"


def _metric_value(value, fallback: float) -> float:
    parsed = _float_or_none(value)
    if parsed is None:
        return round(fallback, 2)
    return round(parsed, 2)


def _float_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_etf_like(ticker: str) -> bool:
    return _fmp_symbol(ticker) in {"IAU", "QQQ", "SPY", "DIA", "IWM"}


def _price_adjusted_fallback_metrics(item: WatchlistItem, quote: MarketQuote | None) -> dict[str, float]:
    if not quote or quote.price <= 0:
        return {"pe": item.pe, "peg": item.peg}
    base_price = _baseline_price(item.ticker, quote.price)
    if base_price <= 0:
        return {"pe": item.pe, "peg": item.peg}
    price_ratio = quote.price / base_price
    return {
        "pe": item.pe * price_ratio,
        "peg": item.peg * price_ratio,
    }


def _baseline_price(ticker: str, current_price: float) -> float:
    fallback = FALLBACK_PRICES.get(ticker)
    if fallback and fallback[0] > 0:
        return fallback[0]
    return current_price
