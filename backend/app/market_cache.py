from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from .models import MarketQuote
from .storage import (
    latest_quote_payloads,
    latest_screening_payload_row,
    load_daily_close_rows,
    save_daily_close_rows,
    save_quote_payloads,
    save_screening_payload_row,
)


MARKET_CACHE_DIR = Path(os.environ.get("MARKET_CACHE_DIR", "data/usstock/market_cache"))
QUOTE_CACHE_DIR = MARKET_CACHE_DIR / "quotes"
DAILY_CLOSE_CACHE_DIR = MARKET_CACHE_DIR / "daily_closes"
SCREENING_CACHE_DIR = MARKET_CACHE_DIR / "screening"


def save_quotes(quotes: list[MarketQuote]) -> None:
    if not quotes:
        return
    save_quote_payloads([quote.model_dump(mode="json") for quote in quotes])
    QUOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = QUOTE_CACHE_DIR / f"{today}.json"
    payload = _read_json(path, default={})
    saved_at = datetime.now().isoformat(timespec="seconds")
    for quote in quotes:
        payload[quote.ticker] = {
            **quote.model_dump(),
            "saved_at": saved_at,
        }
    _write_json(path, payload)


def latest_cached_quotes(tickers: list[str]) -> list[MarketQuote]:
    rows = latest_quote_payloads(tickers)
    if rows:
        return [MarketQuote.model_validate(rows[ticker.upper()]) for ticker in tickers if ticker.upper() in rows]
    if not QUOTE_CACHE_DIR.exists():
        return []
    wanted = {ticker.upper() for ticker in tickers}
    found: dict[str, MarketQuote] = {}
    for path in sorted(QUOTE_CACHE_DIR.glob("*.json"), reverse=True):
        payload = _read_json(path, default={})
        for ticker in list(wanted - found.keys()):
            raw = payload.get(ticker)
            if raw:
                found[ticker] = MarketQuote.model_validate(raw)
        if wanted.issubset(found.keys()):
            break
    return [found[ticker] for ticker in tickers if ticker in found]


def save_daily_closes(ticker: str, series: list[tuple[str, float]]) -> None:
    if not series:
        return
    save_daily_close_rows(ticker, series)
    DAILY_CLOSE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = DAILY_CLOSE_CACHE_DIR / f"{_safe_ticker(ticker)}.json"
    payload = _read_json(path, default={})
    for date, close in series:
        payload[date] = close
    _write_json(path, dict(sorted(payload.items())))


def cached_daily_closes(ticker: str, start_date: str, end_date: str) -> list[tuple[str, float]]:
    rows = load_daily_close_rows(ticker, start_date, end_date)
    if rows:
        return rows
    path = DAILY_CLOSE_CACHE_DIR / f"{_safe_ticker(ticker)}.json"
    payload = _read_json(path, default={})
    if not payload:
        return []
    return [
        (date, round(float(close), 4))
        for date, close in sorted(payload.items())
        if start_date <= date <= end_date and close is not None
    ]


def save_screening_payload(name: str, payload) -> None:
    save_screening_payload_row(name, payload)
    SCREENING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = SCREENING_CACHE_DIR / f"{today}_{name}.json"
    _write_json(path, payload)


def latest_screening_payload(name: str):
    row = latest_screening_payload_row(name)
    if row is not None:
        return row
    if not SCREENING_CACHE_DIR.exists():
        return None
    paths = sorted(SCREENING_CACHE_DIR.glob(f"*_{name}.json"), reverse=True)
    if not paths:
        return None
    return _read_json(paths[0], default=None)


def _safe_ticker(ticker: str) -> str:
    return ticker.upper().replace("/", "_").replace(".", "_")


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
