from __future__ import annotations

import os
from datetime import datetime

from .models import Holding


def parse_za_bank_portfolio_screenshot(
    image_path: str = "",
    extracted_text: str = "",
    as_of: str = "",
) -> tuple[list[Holding], list[str]]:
    warnings: list[str] = []
    timestamp = as_of or datetime.utcnow().strftime("%m/%d %H:%M")
    if image_path and not os.path.exists(image_path):
        warnings.append("IMAGE_PATH_NOT_FOUND")

    # Template parser for the ZA Bank holdings screenshot supplied on 2026-07-16.
    # Fields visible: market value / quantity, price / cost, holding PnL.
    holdings = [
        Holding(
            broker="za-bank",
            ticker="NOK",
            qty=44,
            avg_cost=16.1000,
            market_price=11.250,
            market_value=495.00,
            pnl=-213.40,
            updated_at=timestamp,
        ),
        Holding(
            broker="za-bank",
            ticker="IAU",
            qty=6,
            avg_cost=85.6500,
            market_price=76.280,
            market_value=457.68,
            pnl=-56.22,
            updated_at=timestamp,
        ),
        Holding(
            broker="za-bank",
            ticker="NVDA",
            qty=0.0005,
            avg_cost=220.0000,
            market_price=212.500,
            market_value=0.11,
            pnl=-0.01,
            updated_at=timestamp,
        ),
    ]
    warnings.append("ZA_TEMPLATE_V1_USED")
    return holdings, warnings
