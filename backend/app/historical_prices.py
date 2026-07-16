from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

from .models import MarketQuote


PREVIOUS_CLOSE_FALLBACK = {
    "NOK.US": ("NOK", 11.25, -0.45, -3.85),
    "NOK": ("NOK", 11.25, -0.45, -3.85),
    "SMR.US": ("SMR", 8.36, -0.24, -2.79),
    "IAU": ("IAU", 76.28, 0.01, 0.01),
    "NVDA": ("NVDA", 212.5, 0.7, 0.33),
}

_DAILY_CLOSE_CACHE: dict[tuple[str, str, str], list[tuple[str, float]]] = {}


def previous_close_quotes(tickers: list[str]) -> tuple[list[MarketQuote], list[str]]:
    quotes: list[MarketQuote] = []
    warnings: list[str] = []
    for ticker in tickers:
        try:
            quotes.append(_yahoo_previous_close(ticker))
        except Exception as exc:
            warnings.append(f"{ticker}_YAHOO_FALLBACK:{type(exc).__name__}")
            quotes.append(_fallback_previous_close(ticker))
    return quotes, warnings


def daily_close_series(ticker: str, start_date: str, end_date: str) -> list[tuple[str, float]]:
    cache_key = (ticker, start_date, end_date)
    if cache_key in _DAILY_CLOSE_CACHE:
        return _DAILY_CLOSE_CACHE[cache_key]
    yahoo_symbol = _yahoo_symbol(ticker)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    # Yahoo's period2 is exclusive; add one day so the requested end date is included.
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        f"?period1={int(start.timestamp())}&period2={int(end.timestamp())}&interval=1d"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=12) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    series = [
        (datetime.fromtimestamp(ts).strftime("%Y-%m-%d"), round(float(close), 4))
        for ts, close in zip(timestamps, closes)
        if close is not None
    ]
    if len(series) < 2:
        raise ValueError(f"insufficient historical closes for {ticker}")
    _DAILY_CLOSE_CACHE[cache_key] = series
    return series


def validate_yahoo_ticker(ticker: str) -> MarketQuote:
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("empty ticker")
    if not all(ch.isalnum() or ch in {".", "-"} for ch in normalized):
        raise ValueError("ticker contains unsupported characters")
    quote = _yahoo_previous_close(normalized)
    if quote.price <= 0:
        raise ValueError("ticker has no valid price")
    return quote


def _yahoo_previous_close(ticker: str) -> MarketQuote:
    yahoo_symbol = _yahoo_symbol(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?range=5d&interval=1d"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    valid = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
    if not valid:
        raise ValueError("no closes")
    current_ts, current_close = valid[-1]
    previous_close = valid[-2][1] if len(valid) > 1 else current_close
    change = float(current_close) - float(previous_close)
    pct_change = change / float(previous_close) * 100 if previous_close else 0.0
    return MarketQuote(
        ticker=ticker,
        name=ticker,
        price=round(float(current_close), 4),
        change=round(change, 4),
        pct_change=round(pct_change, 2),
        volume=0,
        source="Yahoo previous close",
        delay_seconds=0,
        updated_at=datetime.fromtimestamp(current_ts).strftime("%m/%d %H:%M"),
    )


def _fallback_previous_close(ticker: str) -> MarketQuote:
    _, price, change, pct_change = PREVIOUS_CLOSE_FALLBACK.get(ticker, (ticker, 100.0, 0.0, 0.0))
    return MarketQuote(
        ticker=ticker,
        name=ticker,
        price=price,
        change=change,
        pct_change=pct_change,
        volume=0,
        source="fallback previous close",
        delay_seconds=0,
        updated_at="07/15 16:00",
    )


def _yahoo_symbol(ticker: str) -> str:
    base = ticker.upper().replace(".US", "")
    if base == "NOK":
        return "NOK"
    if base == "SMR":
        return "SMR"
    return base
