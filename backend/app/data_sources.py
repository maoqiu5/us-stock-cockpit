from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from .models import DataSourceStatus, MarketQuote
from .historical_prices import is_us_market_open, previous_close_quotes
from .seed import WATCHLIST


FALLBACK_PRICES = {
    "NOK.US": (11.23, 0.0, 0.0, 0),
    "SMR.US": (8.36, 0.0, 0.0, 0),
    "NOK": (11.25, -0.45, -3.85, 0),
    "IAU": (76.28, 0.01, 0.01, 0),
    "NVDA": (212.5, 0.0, 0.0, 0),
}


def data_source_statuses() -> list[DataSourceStatus]:
    return [
        DataSourceStatus(
            id="akshare",
            name="AKShare",
            purpose="美股实时/准实时公开行情",
            configured=_module_available("akshare"),
            status="active" if _module_available("akshare") else "fallback",
            detail="已安装时使用 stock_us_spot_em；未安装时使用内置样例行情保持系统可运行。",
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
            purpose="民生银行黄金实时买卖价盯盘",
            configured=True,
            status="manual",
            detail="第一版使用民生银行截图价作为本地基准，并预留银行黄金实时接口适配器。",
        ),
    ]


def market_quotes(symbols: Iterable[str] | None = None) -> list[MarketQuote]:
    tickers = [symbol.upper() for symbol in (symbols or FALLBACK_PRICES.keys())]
    if not is_us_market_open():
        quotes, _ = previous_close_quotes(tickers)
        return quotes
    try:
        return _akshare_quotes(tickers)
    except Exception:
        return [_fallback_quote(ticker) for ticker in tickers]


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
