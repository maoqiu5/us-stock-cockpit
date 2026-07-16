from __future__ import annotations

import json
from datetime import datetime
from urllib.request import Request, urlopen

from .models import MarketQuote


PREVIOUS_CLOSE_FALLBACK = {
    "NOK.US": ("NOK", 11.25, -0.45, -3.85),
    "NOK": ("NOK", 11.25, -0.45, -3.85),
    "SMR.US": ("SMR", 8.36, -0.24, -2.79),
    "IAU": ("IAU", 76.28, 0.01, 0.01),
    "NVDA": ("NVDA", 212.5, 0.7, 0.33),
}


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
