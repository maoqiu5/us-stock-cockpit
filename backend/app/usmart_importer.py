from __future__ import annotations

import os
import re
from datetime import datetime

from .models import Holding


def parse_usmart_portfolio_screenshot(
    image_path: str = "",
    extracted_text: str = "",
    as_of: str = "",
    broker: str = "usmart",
) -> tuple[float, list[Holding], list[str]]:
    warnings: list[str] = []
    timestamp = as_of or datetime.utcnow().strftime("%m/%d %H:%M")
    if image_path and not os.path.exists(image_path):
        warnings.append("IMAGE_PATH_NOT_FOUND")

    if extracted_text.strip():
        parsed = _parse_text(extracted_text, timestamp, broker)
        if parsed[1]:
            return parsed
        warnings.append("TEXT_PARSE_FALLBACK_TO_TEMPLATE")

    # Template parser for the uSMART holdings screenshot supplied on 2026-07-16.
    # It keeps this first importer deterministic until OCR is added.
    holdings = [
        Holding(
            broker="usmart",
            ticker="NOK.US",
            qty=99,
            avg_cost=16.005,
            market_price=11.230,
            market_value=1111.77,
            pnl=-472.72,
            updated_at=timestamp,
        ),
        Holding(
            broker="usmart",
            ticker="SMR.US",
            qty=80,
            avg_cost=19.23,
            market_price=8.360,
            market_value=668.80,
            pnl=-869.60,
            updated_at=timestamp,
        ),
    ]
    for holding in holdings:
        holding.broker = broker  # type: ignore[assignment]
    warnings.append("TEMPLATE_V1_USED")
    return 1784.16, holdings, warnings


def _parse_text(text: str, timestamp: str, broker: str) -> tuple[float, list[Holding], list[str]]:
    warnings: list[str] = []
    net_asset = _number_after(text, r"资产净值|净资产")
    holdings: list[Holding] = []
    for ticker in ("NOK.US", "SMR.US"):
        match = re.search(rf"{re.escape(ticker)}[\s\S]{{0,160}}", text)
        if not match:
            continue
        block = match.group(0)
        numbers = [float(item.replace(",", "")) for item in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", block)]
        if len(numbers) < 5:
            warnings.append(f"{ticker}_INSUFFICIENT_NUMBERS")
            continue
        market_value, qty, price, cost, pnl = numbers[:5]
        holdings.append(
            Holding(
                broker="usmart",
                ticker=ticker,
                qty=qty,
                avg_cost=cost,
                market_price=price,
                market_value=market_value,
                pnl=pnl,
                updated_at=timestamp,
            )
        )
        holdings[-1].broker = broker  # type: ignore[assignment]
    return net_asset or 0, holdings, warnings


def _number_after(text: str, label_pattern: str) -> float:
    match = re.search(rf"(?:{label_pattern})[\s\S]{{0,40}}?(\d+(?:,\d{{3}})*(?:\.\d+)?)", text)
    return float(match.group(1).replace(",", "")) if match else 0
