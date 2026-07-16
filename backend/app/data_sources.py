from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

from .models import DataSourceStatus, MarketQuote
from .seed import WATCHLIST


FALLBACK_PRICES = {
    "AAPL": (213.4, 1.12, 0.53, 51234000),
    "MSFT": (503.1, -0.8, -0.16, 23122000),
    "NVDA": (164.8, -3.4, -2.02, 199420000),
    "AMZN": (226.2, 2.7, 1.21, 40123000),
    "GOOGL": (184.6, 1.9, 1.04, 28770000),
    "META": (712.4, 8.6, 1.22, 17450000),
    "TSLA": (319.8, -4.9, -1.51, 87221000),
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
    ]


def market_quotes(symbols: Iterable[str] | None = None) -> list[MarketQuote]:
    tickers = [symbol.upper() for symbol in (symbols or FALLBACK_PRICES.keys())]
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
                ticker=ticker,
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
