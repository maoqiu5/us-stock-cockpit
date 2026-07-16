from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import DataSourceStatus, Holding, MarketQuote, WatchlistItem
from .historical_prices import _yahoo_intraday_quote, is_us_market_open, previous_close_quotes
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
        return quotes
    try:
        return _fmp_quotes(tickers)
    except Exception:
        pass
    try:
        return _akshare_quotes(tickers)
    except Exception:
        return _yahoo_quotes(tickers)


def dynamic_watchlist(items: list[WatchlistItem], holdings: list[Holding] | None = None, validation: dict[str, dict[str, float | str]] | None = None) -> list[WatchlistItem]:
    tickers = [item.ticker for item in items]
    quotes = {quote.ticker: quote for quote in market_quotes(tickers)}
    holding_map = _holding_context(holdings or [])
    output: list[WatchlistItem] = []
    for item in items:
        quote = quotes.get(item.ticker)
        fundamentals = _fundamentals_for_ticker(item.ticker, quote.price if quote else None)
        output.append(_dynamic_watchlist_item(item, quote, fundamentals, holding_map.get(item.ticker), (validation or {}).get(item.ticker)))
    return output


def _dynamic_watchlist_item(item: WatchlistItem, quote: MarketQuote | None, fundamentals: dict[str, float | str], holding: dict[str, float] | None = None, validation: dict[str, float | str] | None = None) -> WatchlistItem:
    pct_change = quote.pct_change if quote else 0
    trend = _trend_from_change(pct_change)
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
    eligible = pe <= 40 and peg <= 2 and roi >= 15 and growth >= 8 and trend in {"上行", "横盘"} and model_pass
    holding_risk = holding is not None and (holding_pnl_pct <= -15 or holding_weight >= 12)
    model_risk = has_model_validation and model_score < 40
    signal = "RISK" if holding_risk or model_risk or trend == "过热" or pe > 45 or peg > 2.6 or pct_change < -5 else ("BUY" if eligible else "WATCH")
    signal_reason = _signal_reason(signal, pe, peg, roi, growth, trend, pct_change, holding_pnl_pct, holding_weight, holding is not None, model_score, model_reason, has_model_validation)
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


def _signal_reason(signal: str, pe: float, peg: float, roi: float, growth: float, trend: str, pct_change: float, holding_pnl_pct: float, holding_weight: float, has_holding: bool, model_score: int, model_reason: str, has_model_validation: bool) -> str:
    reasons: list[str] = []
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
