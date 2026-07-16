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


class GoldTrendPoint(BaseModel):
    time: str
    price: float


class GoldMonitor(BaseModel):
    product_code: str
    product_name: str
    product_type: str
    trading_status: str
    risk_level: str
    currency: str
    planned_capital: float
    live_price: float
    change: float
    pct_change: float
    day_high: float
    day_low: float
    reference_price: float
    quote_time: str
    min_purchase_amount: float
    increment_amount: float
    buy_fee_rate: float
    estimated_grams: float
    first_order_amount: float
    first_order_grams: float
    reserve_cash: float
    remaining_capital: float
    holding_grams: float
    holding_cost: float
    holding_market_value: float
    holding_pnl: float
    holding_pnl_pct: float
    average_cost: float
    reference_symbol: str
    reference_name: str
    reference_change_pct: float
    reference_time: str
    is_trading_session: bool
    refresh_seconds: int
    trend_points: list[GoldTrendPoint]
    trade_rule: str
    settlement_rule: str
    action: str
    confidence: float
    advice: str
    watch_points: list[str]
    source: str


class GoldManualTrade(BaseModel):
    id: str
    product_code: str = "CMBC-AU"
    product_name: str = "民生积存金"
    side: Side = Side.buy
    amount_cny: float = Field(gt=0)
    grams: float = Field(gt=0)
    price: float = Field(gt=0)
    executed_at: str
    note: str = ""


class GoldManualTradeRequest(BaseModel):
    side: Side = Side.buy
    amount_cny: float = Field(gt=0)
    grams: Optional[float] = Field(default=None, gt=0)
    price: float = Field(gt=0)
    executed_at: str
    note: str = ""


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


class PreviousCloseImportResult(BaseModel):
    as_of: str
    source: str
    imported: int
    account_total: float
    total_pnl: float
    quotes: list[MarketQuote]
    holdings: list[Holding]
    warnings: list[str]


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


class USmartScreenshotImportRequest(BaseModel):
    broker: Literal["za-bank", "usmart"] = "usmart"
    image_path: str = ""
    extracted_text: str = ""
    as_of: str = ""


class USmartScreenshotImportResult(BaseModel):
    broker: Literal["za-bank", "usmart"]
    image_path: str
    net_asset: float
    imported_holdings: int
    warnings: list[str]
    holdings: list[Holding]


class ZABankScreenshotImportRequest(BaseModel):
    image_path: str = ""
    extracted_text: str = ""
    as_of: str = ""


class ZABankScreenshotImportResult(BaseModel):
    broker: Literal["za-bank"] = "za-bank"
    image_path: str
    imported_holdings: int
    warnings: list[str]
    holdings: list[Holding]


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
    ticker: str = "NOK.US"
    start_date: str = "2026-05-01"
    end_date: str = "2026-07-16"
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


class AddWatchlistRequest(BaseModel):
    ticker: str
    name: str = ""
    sector: str = "User Added"


class ValidateTickerResult(BaseModel):
    ticker: str
    valid: bool
    name: str = ""
    price: float = 0
    pct_change: float = 0
    source: str = ""
    market_open: bool = False
    updated_at: str = ""
    reason: str = ""


class HoldingAdvice(BaseModel):
    ticker: str
    broker: str
    action: str
    confidence: float
    reason: str
    risk_level: Literal["low", "medium", "high"]
    suggested_weight: float


class CandidateStock(BaseModel):
    ticker: str
    name: str
    sector: str
    score: int
    reason: str
    action: str


class AllocationSuggestion(BaseModel):
    ticker: str
    current_weight: float
    target_weight: float
    action: str
    amount: float
    reason: str


class PortfolioOptimization(BaseModel):
    account_total: float
    cash_balance: float
    cash_target: float
    cash_action: str
    suggestions: list[AllocationSuggestion]


class ModelValidationItem(BaseModel):
    strategy_id: str
    tested: int
    best_ticker: str
    average_annual_return: float
    average_max_drawdown: float
    tuning_note: str


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
