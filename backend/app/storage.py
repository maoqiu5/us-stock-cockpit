from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", "data/usstock/usstock_cockpit.db"))


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_quotes (
                ticker TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                payload TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                PRIMARY KEY (ticker, trade_date)
            );

            CREATE INDEX IF NOT EXISTS idx_market_quotes_ticker_saved
                ON market_quotes (ticker, saved_at DESC);

            CREATE TABLE IF NOT EXISTS daily_closes (
                ticker TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                close REAL NOT NULL,
                saved_at TEXT NOT NULL,
                PRIMARY KEY (ticker, trade_date)
            );

            CREATE TABLE IF NOT EXISTS screening_payloads (
                name TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                payload TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                PRIMARY KEY (name, trade_date)
            );
            """
        )


def load_app_state() -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT payload FROM app_state WHERE key = 'main'").fetchone()
    if not row:
        return None
    return json.loads(row["payload"])


def save_app_state(payload: dict[str, Any]) -> None:
    init_db()
    saved_at = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_state (key, payload, updated_at)
            VALUES ('main', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (json.dumps(payload, ensure_ascii=False, sort_keys=True), saved_at),
        )


def save_quote_payloads(quotes: list[dict[str, Any]]) -> None:
    if not quotes:
        return
    init_db()
    trade_date = datetime.now().strftime("%Y-%m-%d")
    saved_at = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO market_quotes (ticker, trade_date, payload, saved_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, trade_date) DO UPDATE SET
                payload = excluded.payload,
                saved_at = excluded.saved_at
            """,
            [
                (
                    quote["ticker"].upper(),
                    trade_date,
                    json.dumps({**quote, "saved_at": saved_at}, ensure_ascii=False, sort_keys=True),
                    saved_at,
                )
                for quote in quotes
            ],
        )


def latest_quote_payloads(tickers: list[str]) -> dict[str, dict[str, Any]]:
    init_db()
    wanted = [ticker.upper() for ticker in tickers]
    if not wanted:
        return {}
    placeholders = ",".join("?" for _ in wanted)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT ticker, payload
            FROM (
                SELECT ticker, payload,
                    ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY saved_at DESC, trade_date DESC) AS rn
                FROM market_quotes
                WHERE ticker IN ({placeholders})
            )
            WHERE rn = 1
            """,
            wanted,
        ).fetchall()
    return {row["ticker"]: json.loads(row["payload"]) for row in rows}


def save_daily_close_rows(ticker: str, series: list[tuple[str, float]]) -> None:
    if not series:
        return
    init_db()
    saved_at = datetime.now().isoformat(timespec="seconds")
    normalized = ticker.upper()
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO daily_closes (ticker, trade_date, close, saved_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, trade_date) DO UPDATE SET
                close = excluded.close,
                saved_at = excluded.saved_at
            """,
            [(normalized, date, close, saved_at) for date, close in series],
        )


def load_daily_close_rows(ticker: str, start_date: str, end_date: str) -> list[tuple[str, float]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT trade_date, close
            FROM daily_closes
            WHERE ticker = ? AND trade_date >= ? AND trade_date <= ?
            ORDER BY trade_date
            """,
            (ticker.upper(), start_date, end_date),
        ).fetchall()
    return [(row["trade_date"], round(float(row["close"]), 4)) for row in rows]


def save_screening_payload_row(name: str, payload: Any) -> None:
    init_db()
    trade_date = datetime.now().strftime("%Y-%m-%d")
    saved_at = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO screening_payloads (name, trade_date, payload, saved_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name, trade_date) DO UPDATE SET
                payload = excluded.payload,
                saved_at = excluded.saved_at
            """,
            (name, trade_date, json.dumps(payload, ensure_ascii=False, sort_keys=True), saved_at),
        )


def latest_screening_payload_row(name: str) -> Any:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT payload
            FROM screening_payloads
            WHERE name = ?
            ORDER BY saved_at DESC, trade_date DESC
            LIMIT 1
            """,
            (name,),
        ).fetchone()
    return json.loads(row["payload"]) if row else None
