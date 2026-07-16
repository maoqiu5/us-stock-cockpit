from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class Side(str, Enum):
    buy = "BUY"
    sell = "SELL"


class StrategyModel(BaseModel):
    id: str
    name: str
    factor_set: list[str]
    universe: list[str]
    status: str
    score: int
    annual_return: float
    max_drawdown: float
    trades: int
    description: str
    backtest_config: dict[str, Union[str, int, float]]


class Signal(BaseModel):
    ticker: str
    strategy_id: str
    side: Side
    confidence: float = Field(ge=0, le=1)
    reason: str
    expires_at: str


class RiskDecision(BaseModel):
    allowed: bool
    blocked_reason: str
    position_limit: float
    total_exposure_limit: float
    daily_loss_state: str
    daily_loss_limit: float
    weekly_loss_limit: float


class TradeOrder(BaseModel):
    id: str
    broker: str
    ticker: str
    side: Side
    qty: int
    order_type: str
    limit_price: float
    status: str
    created_at: str


class MarketQuote(BaseModel):
    ticker: str
    name: str = ""
    price: float
    change: float
    pct_change: float
    volume: float = 0
    source: str
    delay_seconds: int
    updated_at: str


class DataSourceStatus(BaseModel):
    id: str
    name: str
    purpose: str
    configured: bool
    status: Literal["active", "fallback", "missing", "manual"]
    detail: str


class Holding(BaseModel):
    broker: Literal["za-bank", "usmart", "ibkr", "manual"]
    ticker: str
    qty: float
    avg_cost: float
    market_price: float
    market_value: float
    pnl: float
    currency: str = "USD"
    updated_at: str


class BrokerImportRecord(BaseModel):
    broker: Literal["za-bank", "usmart", "ibkr", "manual"]
    record_type: Literal["holding", "trade"]
    ticker: str
    side: Optional[Side] = None
    qty: float
    price: float
    executed_at: str
    note: str = ""


class BrokerImportRequest(BaseModel):
    broker: Literal["za-bank", "usmart", "ibkr", "manual"]
    records: list[BrokerImportRecord]


class BrokerImportResult(BaseModel):
    imported: int
    holdings_updated: int
    trades_recorded: int
    message: str


class PreparedBrokerRequest(BaseModel):
    broker: str
    url: str
    method: str
    headers: dict[str, str]
    body: dict[str, Union[str, int, float, bool]]
    ready_to_submit: bool
    blockers: list[str]


class BacktestPoint(BaseModel):
    date: str
    equity: float
    benchmark: float


class BacktestResult(BaseModel):
    strategy_id: str
    ticker: str
    annual_return: float
    pnl: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    trades: int
    benchmark_return: float
    records: list[BacktestPoint]


class BacktestRequest(BaseModel):
    ticker: str = "META"
    start_date: str = "2026-05-01"
    end_date: str = "2026-06-22"
    mode: Literal["offline", "backtest", "paper"] = "offline"


class WatchlistItem(BaseModel):
    ticker: str
    name: str
    sector: str
    pe: float
    peg: float
    roi: float
    growth: float
    trend: str
    eligible: bool
    signal: str


class DisciplineEvent(BaseModel):
    id: str
    ticker: str
    title: str
    reason: str
    action: str
    severity: Literal["ok", "warn", "risk"]
    created_at: str


class OrderRequest(BaseModel):
    ticker: str
    side: Side
    qty: int = Field(gt=0)
    order_type: Literal["LMT", "MKT"] = "LMT"
    limit_price: float = Field(gt=0)
    strategy_id: str = "pe_v1"
    dry_run: bool = True


class ManualExecutionRequest(BaseModel):
    broker: Literal["za-bank", "usmart", "ibkr", "other"] = "za-bank"
    ticker: str
    side: Side
    qty: int = Field(gt=0)
    price: float = Field(gt=0)
    executed_at: str
    note: str = ""


class BrokerCapability(BaseModel):
    id: str
    name: str
    status: Literal["tradable", "manual", "backup"]
    supports_us_stock_orders: bool
    integration: str
    notes: list[str]


class ExecutionConfig(BaseModel):
    mode: Literal["paper", "usmart-paper", "usmart-live", "ibkr-paper", "ibkr-live", "za-manual"]
    live_trading_enabled: bool
    ibkr_host: str
    ibkr_port: int
    ibkr_client_id: int
    usmart_base_url: str
    usmart_channel: str
    notes: list[str]
