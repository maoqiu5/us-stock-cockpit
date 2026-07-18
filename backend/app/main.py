from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .broker import USmartBrokerAdapter, broker_capabilities, broker_from_env, execution_config
from .data_sources import data_source_statuses, dynamic_watchlist, market_quotes
from .gold_monitor import gold_monitor_snapshot
from .historical_prices import is_us_market_open, previous_close_quotes, validate_yahoo_ticker
from .market_cache import latest_screening_payload, save_quotes, save_screening_payload
from .models import AccountBalance, AddWatchlistRequest, AllocationSuggestion, BacktestRequest, BrokerImportRequest, BrokerImportResult, CandidateStock, DisciplineEvent, GoldManualTrade, GoldManualTradeRequest, GoldMonitor, Holding, HoldingAdvice, ManualExecutionRequest, ModelValidationItem, OrderRequest, PortfolioOptimization, PreviousCloseImportResult, Signal, TradeOrder, TradePlanItem, USmartScreenshotImportRequest, USmartScreenshotImportResult, ValidateTickerResult, WatchlistItem, ZABankScreenshotImportRequest, ZABankScreenshotImportResult, MarketQuote
from .risk import RiskConfig, RiskEngine
from .seed import EVENTS, HOLDINGS, ORDERS, STRATEGIES, WATCHLIST
from .strategy import generate_signal, run_backtest
from .storage import init_db, load_app_state, save_app_state
from .usmart_importer import parse_usmart_portfolio_screenshot
from .za_importer import parse_za_bank_portfolio_screenshot

app = FastAPI(title="美股驾驶舱 API", version="0.1.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-App-Password"],
)

CASH_BALANCE = 3.59
ACCOUNT_CASH_BALANCES = {
    "usmart": 3.59,
    "za-bank": 0.0,
    "ibkr": 0.0,
    "manual": 0.0,
}
ACCOUNT_NAMES = {
    "usmart": "uSMART",
    "za-bank": "ZA Bank",
    "ibkr": "IBKR",
    "manual": "手工账户",
}

state = {
    "automation_paused": False,
    "quote_snapshot": None,
    "quote_snapshot_source": "",
    "quote_snapshot_as_of": "",
}

GOLD_MANUAL_TRADES: list[GoldManualTrade] = []
LOCAL_STATE_PATH = Path(os.environ.get("LOCAL_STATE_PATH", "data/usstock/local_state.json"))
MODEL_VALIDATION_BY_TICKER: dict[str, dict[str, float | str]] = {}
MODEL_VALIDATION_PERIODS = {
    "short": ("2026-05-01", "2026-07-16", 0.30),
    "medium": ("2025-07-16", "2026-07-16", 0.50),
    "long": ("2023-07-16", "2026-07-16", 0.20),
}
SCREENING_CACHE_SECONDS = 15 * 60
SCREENING_CACHE: tuple[float, list[CandidateStock]] | None = None
LOW_PRICE_CANDIDATE_LIMIT = 12


def _load_local_state() -> None:
    init_db()
    payload = load_app_state()
    if payload is None:
        if not LOCAL_STATE_PATH.exists():
            _save_local_state()
            return
        payload = json.loads(LOCAL_STATE_PATH.read_text(encoding="utf-8"))
        save_app_state(payload)
    _apply_local_state_payload(payload)


def _apply_local_state_payload(payload: dict) -> None:
    if not payload:
        return
    WATCHLIST[:] = [WatchlistItem.model_validate(item) for item in payload.get("watchlist", [])] or WATCHLIST
    HOLDINGS[:] = [Holding.model_validate(item) for item in payload.get("holdings", [])] or HOLDINGS
    EVENTS[:] = [DisciplineEvent.model_validate(item) for item in payload.get("events", [])] or EVENTS
    ORDERS[:] = [TradeOrder.model_validate(item) for item in payload.get("orders", [])] or ORDERS
    GOLD_MANUAL_TRADES[:] = [GoldManualTrade.model_validate(item) for item in payload.get("gold_manual_trades", [])]
    ACCOUNT_CASH_BALANCES.update({
        broker: round(float(value), 2)
        for broker, value in payload.get("account_cash_balances", {}).items()
        if broker in ACCOUNT_CASH_BALANCES
    })
    saved_state = payload.get("state", {})
    state.update({
        "automation_paused": saved_state.get("automation_paused", state["automation_paused"]),
        "quote_snapshot": [MarketQuote.model_validate(item) for item in saved_state.get("quote_snapshot") or []] or None,
        "quote_snapshot_source": saved_state.get("quote_snapshot_source", state["quote_snapshot_source"]),
        "quote_snapshot_as_of": saved_state.get("quote_snapshot_as_of", state["quote_snapshot_as_of"]),
    })


def _save_local_state() -> None:
    payload = {
        "watchlist": [item.model_dump(mode="json") for item in WATCHLIST],
        "holdings": [item.model_dump(mode="json") for item in HOLDINGS],
        "events": [item.model_dump(mode="json") for item in EVENTS],
        "orders": [item.model_dump(mode="json") for item in ORDERS],
        "gold_manual_trades": [item.model_dump(mode="json") for item in GOLD_MANUAL_TRADES],
        "account_cash_balances": ACCOUNT_CASH_BALANCES,
        "state": {
            "automation_paused": state["automation_paused"],
            "quote_snapshot_source": state["quote_snapshot_source"],
            "quote_snapshot_as_of": state["quote_snapshot_as_of"],
            "quote_snapshot": [item.model_dump(mode="json") for item in state["quote_snapshot"]] if state["quote_snapshot"] else None,
        },
    }
    save_app_state(payload)
    LOCAL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_load_local_state()


@app.middleware("http")
async def require_app_password(request: Request, call_next):
    app_password = os.getenv("APP_PASSWORD", "").strip()
    if not app_password or request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)

    header_password = request.headers.get("X-App-Password", "")
    auth_header = request.headers.get("Authorization", "")
    bearer_password = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    if header_password != app_password and bearer_password != app_password:
        return JSONResponse({"detail": "需要访问密码"}, status_code=401)
    return await call_next(request)


def risk_engine() -> RiskEngine:
    return RiskEngine(RiskConfig(automation_paused=state["automation_paused"]))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard/summary")
def dashboard_summary() -> dict:
    total_value = _account_total()
    today_pnl = _dashboard_pnl()
    risk = risk_engine().status()
    quote_source = state["quote_snapshot_source"] or "截图导入"
    saved_at = state["quote_snapshot_as_of"] or "07/16 14:04"
    return {
        "account_total": total_value,
        "today_pnl": today_pnl,
        "pnl_label": "昨收持仓盈亏" if state["quote_snapshot"] else "今日",
        "discipline_score": 62,
        "active_signals": 5,
        "signal_breakdown": {"buy": 0, "sell": 2, "hold": 0, "watch": 3},
        "max_drawdown": -56.53,
        "max_drawdown_limit": -12,
        "execution_mode": "本地对账" if execution_config().mode == "paper" else execution_config().mode,
        "automation_paused": state["automation_paused"],
        "global_risk": "暂停" if state["automation_paused"] else ("已阻断" if not risk.allowed else "正常"),
        "data_source": quote_source,
        "sync_status": "本地已导入",
        "local_saved_at": saved_at,
        "today_orders": "0 / 5",
        "workflow": [
            {"step": 1, "title": "导入持仓", "detail": "ZA 3 / uSMART 2", "status": "done"},
            {"step": 2, "title": "刷行情", "detail": quote_source, "status": "done"},
            {"step": 3, "title": "算盈亏", "detail": f"{'昨收' if state['quote_snapshot'] else '今日'} {today_pnl:+.2f}", "status": "done"},
            {"step": 4, "title": "看风险", "detail": "2 只大回撤", "status": "active"},
            {"step": 5, "title": "记执行", "detail": "截图导入", "status": "active"},
        ],
        "checks": [
            {"severity": "ok", "title": "ZA/uSMART 持仓已导入", "detail": "已从两张截图同步 5 条真实持仓。", "time": "07/16 14:04"},
            {"severity": "risk", "title": "SMR.US 回撤较大", "detail": "持仓盈亏 -56.53%，亏损 -$869.60。", "time": "uSMART 截图 · 07/16 14:02"},
            {"severity": "warn", "title": "NOK 双账户持仓", "detail": "ZA 44 股、uSMART 99 股，合计 143 股。", "time": "ZA/uSMART 合并视图"},
        ],
    }


@app.get("/strategies")
def strategies():
    return STRATEGIES


@app.post("/strategies/{strategy_id}/backtest")
def backtest(strategy_id: str, request: BacktestRequest):
    if strategy_id not in {strategy.id for strategy in STRATEGIES}:
        raise HTTPException(status_code=404, detail="strategy not found")
    try:
        return run_backtest(strategy_id, request.ticker, request.start_date, request.end_date)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"{request.ticker} 缺少可用真实历史数据，无法回测：{type(exc).__name__}") from exc


@app.get("/watchlist")
def watchlist():
    return dynamic_watchlist(WATCHLIST, HOLDINGS, MODEL_VALIDATION_BY_TICKER)


@app.post("/watchlist")
def add_watchlist_item(request: AddWatchlistRequest) -> WatchlistItem:
    global SCREENING_CACHE
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")
    existing = next((item for item in WATCHLIST if item.ticker == ticker), None)
    if existing:
        return existing
    validation = validate_ticker(ticker)
    if not validation.valid:
        raise HTTPException(status_code=400, detail=validation.reason)
    pct_change = validation.pct_change
    trend = "上行" if pct_change > 1 else ("下行" if pct_change < -1 else "横盘")
    item = WatchlistItem(
        ticker=ticker,
        name=request.name or validation.name or f"{ticker} · 手工加入",
        sector=request.sector or "User Added",
        pe=30.0,
        peg=1.8,
        roi=16.0,
        growth=10.0,
        trend=trend,
        eligible=pct_change > -3,
        signal="WATCH" if abs(pct_change) < 3 else "RISK",
    )
    WATCHLIST.append(item)
    SCREENING_CACHE = None
    _save_local_state()
    return item


@app.get("/watchlist/validate")
def validate_ticker(ticker: str = Query(default="")) -> ValidateTickerResult:
    normalized = ticker.strip().upper()
    if not normalized:
        return ValidateTickerResult(ticker="", valid=False, reason="请输入股票代码。")
    market_open = is_us_market_open()
    try:
        quote = validate_yahoo_ticker(normalized)
    except Exception:
        return ValidateTickerResult(ticker=normalized, valid=False, reason=f"未能识别 {normalized}，请检查代码或交易所后缀。")
    price_mode = "交易时段，已拉取 Yahoo 盘中价" if market_open else "休市，已拉取上一交易日收盘价"
    return ValidateTickerResult(
        ticker=normalized,
        valid=True,
        name=quote.name if quote.name and quote.name != normalized else f"{normalized} · Yahoo 已识别",
        price=quote.price,
        pct_change=quote.pct_change,
        source=quote.source,
        market_open=market_open,
        updated_at=quote.updated_at,
        reason=f"{price_mode}，可加入股票池。",
    )


@app.delete("/watchlist/{ticker}")
def delete_watchlist_item(ticker: str) -> dict[str, str]:
    global SCREENING_CACHE
    normalized = ticker.strip().upper()
    holding_tickers = {holding.ticker for holding in HOLDINGS}
    if normalized in holding_tickers:
        raise HTTPException(status_code=400, detail="当前持仓股票不能从股票池删除，请先在持仓纪律里处理。")
    before = len(WATCHLIST)
    WATCHLIST[:] = [item for item in WATCHLIST if item.ticker != normalized]
    if len(WATCHLIST) == before:
        raise HTTPException(status_code=404, detail="ticker not found")
    SCREENING_CACHE = None
    _save_local_state()
    return {"deleted": normalized}


@app.get("/market/quotes")
def quotes(symbols: str = Query(default="")):
    requested = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if state["quote_snapshot"]:
        cached = {quote.ticker: quote for quote in state["quote_snapshot"]}
        wanted = requested or [item.ticker for item in WATCHLIST]
        output = [cached[ticker] for ticker in wanted if ticker in cached]
        save_quotes(output)
        return output
    return market_quotes(requested or [item.ticker for item in WATCHLIST])


@app.post("/market/import-previous-close")
def import_previous_close() -> PreviousCloseImportResult:
    tickers = list(dict.fromkeys(holding.ticker for holding in HOLDINGS))
    quotes, warnings = previous_close_quotes(tickers)
    save_quotes(quotes)
    quote_map = {quote.ticker: quote for quote in quotes}
    for holding in HOLDINGS:
        quote = quote_map.get(holding.ticker)
        if not quote:
            continue
        holding.market_price = quote.price
        holding.market_value = round(holding.qty * quote.price, 2)
        holding.pnl = round((quote.price - holding.avg_cost) * holding.qty, 2)
        holding.updated_at = quote.updated_at
    state["quote_snapshot"] = quotes
    state["quote_snapshot_source"] = "昨收快照"
    state["quote_snapshot_as_of"] = quotes[0].updated_at if quotes else "07/15 16:00"
    EVENTS.insert(
        0,
        DisciplineEvent(
            id=f"evt_prev_close_{len(EVENTS) + 1}",
            ticker="PORTFOLIO",
            title="已导入上一交易日收盘价",
            reason=f"用 {len(quotes)} 条昨收行情重估持仓，可在美股开盘前做策略模型测试。",
            action="允许线下评测，继续阻断自动实盘执行",
            severity="ok",
            created_at=state["quote_snapshot_as_of"],
        ),
    )
    return PreviousCloseImportResult(
        as_of=state["quote_snapshot_as_of"],
        source=state["quote_snapshot_source"],
        imported=len(quotes),
        account_total=_account_total(),
        total_pnl=round(sum(holding.pnl for holding in HOLDINGS), 2),
        quotes=quotes,
        holdings=HOLDINGS,
        warnings=warnings,
    )


@app.get("/data-sources/status")
def source_statuses():
    return data_source_statuses()


@app.get("/gold/monitor")
def gold_monitor() -> GoldMonitor:
    return gold_monitor_snapshot(GOLD_MANUAL_TRADES)


@app.get("/gold/manual-trades")
def gold_manual_trades() -> list[GoldManualTrade]:
    return GOLD_MANUAL_TRADES


@app.post("/gold/manual-trades")
def create_gold_manual_trade(request: GoldManualTradeRequest) -> GoldManualTrade:
    grams = request.grams if request.grams is not None else round(request.amount_cny / request.price, 4)
    trade = GoldManualTrade(
        id=f"gold_manual_{len(GOLD_MANUAL_TRADES) + 1}",
        side=request.side,
        amount_cny=request.amount_cny,
        grams=grams,
        price=request.price,
        executed_at=request.executed_at,
        note=request.note,
    )
    GOLD_MANUAL_TRADES.insert(0, trade)
    EVENTS.insert(
        0,
        DisciplineEvent(
            id=f"evt_{trade.id}",
            ticker="CMBC-AU",
            title="黄金线下操作已记录",
            reason=f"{request.executed_at} {request.side.value} {grams:.4f} 克，成交价 ¥{request.price:.2f}/克，金额 ¥{request.amount_cny:.2f}。",
            action="纳入黄金盯盘和后续仓位纪律分析",
            severity="ok",
            created_at=request.executed_at,
        ),
    )
    _save_local_state()
    return trade


@app.delete("/gold/manual-trades/{trade_id}")
def delete_gold_manual_trade(trade_id: str) -> dict[str, str]:
    index = next((idx for idx, trade in enumerate(GOLD_MANUAL_TRADES) if trade.id == trade_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="gold manual trade not found")
    GOLD_MANUAL_TRADES.pop(index)
    EVENTS[:] = [event for event in EVENTS if event.id != f"evt_{trade_id}"]
    _save_local_state()
    return {"deleted": trade_id}


@app.get("/portfolio/holdings")
def holdings() -> list[Holding]:
    return HOLDINGS


@app.get("/portfolio/account-balances")
def account_balances() -> list[AccountBalance]:
    return _account_balances()


@app.get("/advice/holdings")
def holding_advice() -> list[HoldingAdvice]:
    account_total = max(_account_total(), 1)
    watchlist_by_ticker = {item.ticker: item for item in dynamic_watchlist(WATCHLIST, HOLDINGS, MODEL_VALIDATION_BY_TICKER)}
    advice: list[HoldingAdvice] = []
    for holding in HOLDINGS:
        cost_basis = max(holding.avg_cost * holding.qty, 0.01)
        pnl_pct = holding.pnl / cost_basis * 100
        current_weight = holding.market_value / account_total
        item = watchlist_by_ticker.get(holding.ticker)
        signal = item.signal if item else "WATCH"
        signal_reason = item.signal_reason if item else "无股票池信号。"
        trend = item.trend if item else "未知"
        pe = item.pe if item else 0
        peg = item.peg if item else 0
        roi = item.roi if item else 0
        if pnl_pct <= -35:
            action = "减仓/禁止补仓"
            risk_level = "high"
            confidence = 0.9 if signal == "RISK" else 0.82
            target = min(current_weight, 0.03)
            reason = f"持仓亏损 {pnl_pct:.1f}%，已超过 -35% 强纪律线；股票池信号 {signal}，{signal_reason}"
        elif pnl_pct <= -15:
            action = "持有观察/禁止补仓" if signal == "RISK" else "持有观察"
            risk_level = "high" if signal == "RISK" else "medium"
            confidence = 0.78 if signal == "RISK" else 0.68
            target = min(current_weight, 0.05)
            reason = f"持仓亏损 {pnl_pct:.1f}%，处于 -15% 观察线以下；趋势 {trend}，股票池信号 {signal}。{signal_reason}"
        elif current_weight > 0.12:
            action = "降低集中度" if signal != "BUY" else "只减集中度不加仓"
            risk_level = "medium"
            confidence = 0.72
            target = 0.08
            reason = f"当前权重 {current_weight * 100:.1f}%，超过 12% 单票观察上限；趋势 {trend}，PE {pe:.2f} / PEG {peg:.2f}。"
        elif signal == "RISK":
            action = "暂停加仓"
            risk_level = "medium"
            confidence = 0.7
            target = min(current_weight, 0.05)
            reason = f"持仓暂未触发亏损线，但股票池信号为 RISK：{signal_reason}"
        elif signal == "BUY" and pnl_pct >= -5 and current_weight < 0.05:
            action = "小额加仓候选"
            risk_level = "low"
            confidence = 0.66
            target = min(0.05, current_weight + 0.02)
            reason = f"持仓亏损/盈利 {pnl_pct:.1f}%，仓位 {current_weight * 100:.1f}%，股票池 BUY；PE {pe:.2f} / PEG {peg:.2f} / ROI {roi:.2f}%。"
        else:
            action = "继续跟踪"
            risk_level = "low"
            confidence = 0.58
            target = max(current_weight, 0.02)
            reason = f"未触发强制卖出或加仓条件；趋势 {trend}，股票池信号 {signal}，继续等更明确的价格和因子共振。"
        advice.append(
            HoldingAdvice(
                ticker=holding.ticker,
                broker=holding.broker,
                action=action,
                confidence=confidence,
                reason=reason,
                risk_level=risk_level,
                suggested_weight=round(target * 100, 2),
            )
        )
    return advice


@app.get("/execution/plan")
def execution_plan() -> list[TradePlanItem]:
    account_total = max(_account_total(), 1)
    holding_map = _aggregate_holdings()
    quotes = {quote.ticker: quote for quote in market_quotes([item.ticker for item in WATCHLIST])}
    plans: list[TradePlanItem] = []
    for item in dynamic_watchlist(WATCHLIST, HOLDINGS, MODEL_VALIDATION_BY_TICKER, quotes):
        holding = holding_map.get(item.ticker)
        quote = quotes.get(item.ticker)
        reference_price = quote.price if quote else (holding["price"] if holding else 0)
        current_amount = holding["value"] if holding else 0
        current_weight = current_amount / account_total
        target_weight, reason_bits, blockers = _target_weight_for_plan(item, holding, current_weight)
        target_amount = round(account_total * target_weight, 2)
        raw_delta = target_amount - current_amount
        side = "NONE"
        action = "观察不交易"
        delta_amount = 0.0
        if blockers:
            action = "禁止买入/等待"
        elif raw_delta > 25 and item.signal == "BUY":
            side = "BUY"
            action = "分批买入"
            delta_amount = min(raw_delta, max(_cash_balance() - account_total * 0.08, 0))
            if delta_amount < 25:
                side = "NONE"
                action = "现金不足/等待"
                blockers.append("可用现金低于目标现金垫")
                delta_amount = 0.0
        elif raw_delta < -25:
            side = "SELL"
            action = "减仓到目标"
            delta_amount = raw_delta
        suggested_qty = _suggested_qty(abs(delta_amount), reference_price)
        if side == "SELL" and holding:
            suggested_qty = min(suggested_qty, int(holding["qty"]))
        stop_loss_price, take_profit_price = _execution_price_lines(item, holding, reference_price)
        confidence = _plan_confidence(item, side, blockers)
        plans.append(
            TradePlanItem(
                ticker=item.ticker,
                name=item.name,
                broker=str(holding["broker"] if holding else "watchlist"),
                signal=item.signal,
                model_score=item.model_score,
                action=action,
                side=side,
                current_weight=round(current_weight * 100, 2),
                target_weight=round(target_weight * 100, 2),
                current_amount=round(current_amount, 2),
                target_amount=target_amount,
                delta_amount=round(delta_amount, 2),
                reference_price=round(reference_price, 2),
                suggested_qty=suggested_qty,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                confidence=confidence,
                reason="；".join(reason_bits + ([item.signal_reason] if item.signal_reason else []))[:240],
                blockers=blockers,
            )
        )
    return sorted(plans, key=lambda plan: (plan.side == "NONE", -abs(plan.delta_amount), plan.ticker))


def _aggregate_holdings() -> dict[str, dict[str, float | str]]:
    holdings: dict[str, dict[str, float | str]] = {}
    for holding in HOLDINGS:
        current = holdings.get(holding.ticker, {"qty": 0.0, "value": 0.0, "cost": 0.0, "pnl": 0.0, "price": holding.market_price, "broker": holding.broker})
        current["qty"] = float(current["qty"]) + holding.qty
        current["value"] = float(current["value"]) + holding.market_value
        current["cost"] = float(current["cost"]) + holding.avg_cost * holding.qty
        current["pnl"] = float(current["pnl"]) + holding.pnl
        current["price"] = holding.market_price
        current["broker"] = f"{current['broker']} / {holding.broker}" if holding.broker not in str(current["broker"]) else current["broker"]
        holdings[holding.ticker] = current
    return holdings


def _account_balances() -> list[AccountBalance]:
    holding_values: dict[str, float] = {broker: 0.0 for broker in ACCOUNT_CASH_BALANCES}
    updated_at: dict[str, str] = {broker: "-" for broker in ACCOUNT_CASH_BALANCES}
    for holding in HOLDINGS:
        holding_values[holding.broker] = holding_values.get(holding.broker, 0.0) + holding.market_value
        updated_at[holding.broker] = holding.updated_at
    brokers = sorted(set(ACCOUNT_CASH_BALANCES) | {holding.broker for holding in HOLDINGS})
    balances: list[AccountBalance] = []
    for broker in brokers:
        cash = round(float(ACCOUNT_CASH_BALANCES.get(broker, 0.0)), 2)
        holding_value = round(float(holding_values.get(broker, 0.0)), 2)
        if cash == 0 and holding_value == 0:
            continue
        balances.append(
            AccountBalance(
                broker=broker,
                name=ACCOUNT_NAMES.get(broker, broker),
                available_cash=cash,
                holding_value=holding_value,
                account_total=round(cash + holding_value, 2),
                updated_at=updated_at.get(broker, "-"),
                source="本地账户余额",
            )
        )
    return balances


def _target_weight_for_plan(item: WatchlistItem, holding: dict[str, float | str] | None, current_weight: float) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = [f"股票池信号 {item.signal}", f"模型分 {item.model_score}" if item.model_reason else "模型待验证"]
    blockers: list[str] = []
    pnl_pct = 0.0
    if holding and float(holding["cost"]) > 0:
        pnl_pct = float(holding["pnl"]) / float(holding["cost"]) * 100
        reasons.append(f"持仓盈亏 {pnl_pct:.1f}%")
    if item.signal == "BUY":
        if item.model_score >= 75:
            target = 0.08
        elif item.model_score >= 65:
            target = 0.06
        else:
            target = 0.05
        if current_weight >= 0.12:
            blockers.append("当前单票仓位超过 12%")
            target = min(current_weight, 0.08)
        if item.trend == "下行":
            blockers.append("趋势下行，等待价格企稳")
        reasons.append(f"BUY 目标仓位 {target * 100:.1f}%")
        return target, reasons, blockers
    if item.signal == "RISK":
        if pnl_pct <= -35:
            target = min(current_weight, 0.03)
            reasons.append("超过 -35% 强纪律线")
        elif current_weight >= 0.12:
            target = 0.08
            reasons.append("仓位超过 12%，先降集中度")
        else:
            target = min(current_weight, 0.05)
            reasons.append("RISK 状态禁止补仓")
        if not holding:
            blockers.append("无持仓且 RISK，禁止新开仓")
            target = 0.0
        return target, reasons, blockers
    target = current_weight if holding else 0.0
    reasons.append("WATCH 状态只观察，不主动交易")
    return target, reasons, blockers


def _suggested_qty(amount: float, price: float) -> int:
    if amount < 25 or price <= 0:
        return 0
    return max(1, int(amount // price))


def _execution_price_lines(item: WatchlistItem, holding: dict[str, float | str] | None, reference_price: float) -> tuple[float, float]:
    if reference_price <= 0:
        return 0.0, 0.0
    cost = float(holding["cost"]) / max(float(holding["qty"]), 1) if holding and float(holding["qty"]) > 0 else reference_price
    if item.signal == "RISK":
        stop_loss = min(reference_price * 0.95, cost * 0.85)
        take_profit = reference_price * 1.08
    elif item.signal == "BUY":
        stop_loss = reference_price * 0.92
        take_profit = reference_price * 1.15
    else:
        stop_loss = reference_price * 0.9
        take_profit = reference_price * 1.12
    return round(stop_loss, 2), round(take_profit, 2)


def _plan_confidence(item: WatchlistItem, side: str, blockers: list[str]) -> float:
    if blockers:
        return 0.52
    base = 0.62 if side == "NONE" else 0.7
    if item.model_score >= 65:
        base += 0.08
    if item.signal == "RISK" and side == "SELL":
        base += 0.1
    return round(min(base, 0.9), 2)


@app.get("/screening/candidates")
def screening_candidates() -> list[CandidateStock]:
    global SCREENING_CACHE
    now = time.time()
    if SCREENING_CACHE and SCREENING_CACHE[1] and now - SCREENING_CACHE[0] < SCREENING_CACHE_SECONDS:
        return SCREENING_CACHE[1]
    existing = {item.ticker.replace(".US", "") for item in WATCHLIST}
    pool = [item for item in _low_price_candidate_universe() if item.ticker.replace(".US", "") not in existing]
    dynamic_items = dynamic_watchlist(pool)
    candidates = [_candidate_from_watchlist_item(item) for item in dynamic_items]
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:6]
    save_screening_payload("low_price_candidates", [candidate.model_dump() for candidate in candidates])
    if candidates:
        SCREENING_CACHE = (now, candidates)
    return candidates


def _low_price_candidate_universe() -> list[WatchlistItem]:
    rows = _fmp_low_price_screener()
    pool: list[WatchlistItem] = []
    for row in rows:
        ticker = str(row.get("symbol") or "").upper()
        price = _float_value(row.get("price"))
        if not ticker or price <= 0 or price >= 10:
            continue
        pool.append(
            WatchlistItem(
                ticker=ticker,
                name=str(row.get("companyName") or row.get("name") or ticker),
                sector=str(row.get("sector") or row.get("industry") or "Low Price"),
                pe=30.0,
                peg=1.8,
                roi=12.0,
                growth=8.0,
                trend="横盘",
                eligible=False,
                signal="WATCH",
            )
        )
    return pool[:LOW_PRICE_CANDIDATE_LIMIT]


def _fmp_low_price_screener() -> list[dict]:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        cached = latest_screening_payload("fmp_low_price_raw")
        cached_rows = cached if isinstance(cached, list) and cached else []
        return cached_rows or _finviz_low_price_screener()
    params = urlencode({
        "priceMoreThan": 1,
        "priceLowerThan": 10,
        "marketCapMoreThan": 100_000_000,
        "volumeMoreThan": 500_000,
        "isActivelyTrading": "true",
        "limit": 40,
        "apikey": api_key,
    })
    request = Request(f"https://financialmodelingprep.com/stable/company-screener?{params}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.load(response)
    except Exception:
        cached = latest_screening_payload("fmp_low_price_raw")
        cached_rows = cached if isinstance(cached, list) and cached else []
        return cached_rows or _fmp_stock_screener_v3(api_key) or _fmp_stock_list_low_price(api_key) or _finviz_low_price_screener()
    if not isinstance(payload, list):
        rows = _fmp_stock_screener_v3(api_key) or _fmp_stock_list_low_price(api_key) or _finviz_low_price_screener()
        return rows
    rows = _valid_low_price_rows([row for row in payload if isinstance(row, dict)])
    if not rows:
        rows = _fmp_stock_screener_v3(api_key) or _fmp_stock_list_low_price(api_key) or _finviz_low_price_screener()
    save_screening_payload("fmp_low_price_raw", rows)
    return rows


def _fmp_stock_screener_v3(api_key: str) -> list[dict]:
    params = urlencode({
        "priceMoreThan": 1,
        "priceLowerThan": 10,
        "marketCapMoreThan": 100_000_000,
        "volumeMoreThan": 500_000,
        "isActivelyTrading": "true",
        "limit": 60,
        "apikey": api_key,
    })
    request = Request(f"https://financialmodelingprep.com/api/v3/stock-screener?{params}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.load(response)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    rows = _valid_low_price_rows([row for row in payload if isinstance(row, dict)])
    if rows:
        save_screening_payload("fmp_stock_screener_v3_low_price_raw", rows)
    return rows


def _fmp_stock_list_low_price(api_key: str) -> list[dict]:
    rows = _fmp_stock_list_low_price_from_url(f"https://financialmodelingprep.com/stable/stock-list?{urlencode({'apikey': api_key})}")
    if not rows:
        rows = _fmp_stock_list_low_price_from_url(f"https://financialmodelingprep.com/api/v3/stock/list?{urlencode({'apikey': api_key})}")
    if rows:
        save_screening_payload("fmp_stock_list_low_price_raw", rows)
        return rows
    cached = latest_screening_payload("fmp_stock_list_low_price_raw")
    return cached if isinstance(cached, list) else []


def _finviz_low_price_screener() -> list[dict]:
    url = "https://finviz.com/screener.ashx?v=111&f=sh_avgvol_o500,sh_price_u10,sh_relvol_o1"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        cached = latest_screening_payload("finviz_low_price_raw")
        return cached if isinstance(cached, list) else []
    rows: list[dict] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I):
        ticker_match = re.search(r"stock\?t=([A-Z.\-]+)", row_html)
        if not ticker_match:
            continue
        cells = [_strip_html(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S | re.I)]
        if len(cells) < 10:
            continue
        ticker = ticker_match.group(1).upper()
        price = _float_value(cells[-3])
        if price <= 1 or price >= 10:
            continue
        industry = cells[4] if len(cells) > 4 else "Finviz screener"
        if "exchange traded fund" in industry.lower() or "etf" in industry.lower():
            continue
        rows.append({
            "symbol": ticker,
            "companyName": cells[2] if len(cells) > 2 else ticker,
            "sector": cells[3] if len(cells) > 3 else "Low Price",
            "industry": industry,
            "price": price,
            "source": "Finviz screener",
        })
    rows = rows[:60]
    save_screening_payload("finviz_low_price_raw", rows)
    return rows


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", text).strip()
    cached = latest_screening_payload("fmp_stock_list_low_price_raw")
    return cached if isinstance(cached, list) else []


def _fmp_stock_list_low_price_from_url(url: str) -> list[dict]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    accepted_exchanges = {"NASDAQ", "NYSE", "AMEX"}
    rows: list[dict] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        price = _float_value(row.get("price"))
        exchange = str(row.get("exchangeShortName") or row.get("exchange") or "").upper()
        symbol = str(row.get("symbol") or "").upper()
        stock_type = str(row.get("type") or "stock").lower()
        if not symbol or "." in symbol or price <= 1 or price >= 10:
            continue
        if exchange not in accepted_exchanges:
            continue
        if stock_type not in {"stock", "common stock", ""}:
            continue
        rows.append({
            "symbol": symbol,
            "companyName": row.get("name") or symbol,
            "price": price,
            "sector": row.get("sector") or "Low Price",
            "industry": row.get("industry") or "US listed stock",
            "exchange": exchange,
            "source": "FMP stock-list",
        })
    return rows[:60]


def _valid_low_price_rows(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    for row in rows:
        ticker = str(row.get("symbol") or "").upper()
        price = _float_value(row.get("price"))
        if ticker and 1 < price < 10:
            output.append(row)
    return output


def _candidate_from_watchlist_item(item: WatchlistItem) -> CandidateStock:
    model = _candidate_model_summary(item.ticker)
    third_party = _third_party_reference(item.ticker)
    factor_score = _candidate_factor_score(item)
    trend_score = 100 if item.trend in {"上行", "横盘"} else (60 if item.trend == "过热" else 35)
    reference_bonus = 6 if third_party["sentiment"] == "positive" else (-8 if third_party["sentiment"] == "negative" else 0)
    if model["data_quality"] < 50:
        score = min(39, round(factor_score * 0.45 + trend_score * 0.15))
    else:
        score = round(float(model["score"]) * 0.55 + factor_score * 0.35 + trend_score * 0.10 + reference_bonus)
    score = max(0, min(100, score))
    if score >= 70 and model["data_quality"] >= 80 and item.signal != "RISK":
        action = "加入监控"
    elif score >= 55 and model["data_quality"] >= 50:
        action = "观察等待"
    else:
        action = "暂不加入"
    reason = (
        f"10美元以下真实筛选；{model['best_strategy']} 多周期模型分 {model['score']}，真实数据 {model['data_quality']:.0f}%；"
        f"因子分 {factor_score}，趋势 {item.trend}，股票池信号 {item.signal}；{third_party['summary']}。"
    )
    if model["missing_samples"]:
        reason += f" 缺失 {model['missing_samples']} 个回测样本。"
    return CandidateStock(
        ticker=item.ticker,
        name=item.name,
        sector=item.sector,
        price=_candidate_price(item.ticker),
        score=score,
        reason=reason,
        action=action,
        model_score=int(model["score"]),
        data_quality=round(float(model["data_quality"]), 2),
        signal=item.signal,
        reference_source=str(third_party["source"]),
    )


def _candidate_price(ticker: str) -> float:
    try:
        quotes = market_quotes([ticker])
        return round(quotes[0].price, 2) if quotes else 0
    except Exception:
        return 0


def _third_party_reference(ticker: str) -> dict[str, str]:
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return {"source": "FMP analyst grades unavailable", "sentiment": "neutral", "summary": "第三方评级暂不可用"}
    params = urlencode({"symbol": ticker, "apikey": api_key})
    request = Request(f"https://financialmodelingprep.com/stable/grades-consensus?{params}", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.load(response)
    except Exception:
        return {"source": "FMP analyst grades", "sentiment": "neutral", "summary": "第三方评级未返回"}
    row = payload[0] if isinstance(payload, list) and payload else {}
    if not isinstance(row, dict):
        return {"source": "FMP analyst grades", "sentiment": "neutral", "summary": "第三方评级为空"}
    buy = int(_float_value(row.get("strongBuy")) + _float_value(row.get("buy")))
    sell = int(_float_value(row.get("sell")) + _float_value(row.get("strongSell")))
    hold = int(_float_value(row.get("hold")))
    sentiment = "positive" if buy > sell and buy >= hold else ("negative" if sell > buy else "neutral")
    return {
        "source": "FMP analyst grades consensus",
        "sentiment": sentiment,
        "summary": f"第三方评级参考 买入 {buy} / 持有 {hold} / 卖出 {sell}",
    }


def _candidate_factor_score(item: WatchlistItem) -> int:
    if item.sector.upper() == "ETF":
        return 72 if item.trend in {"上行", "横盘"} else 45
    checks = [
        item.pe <= 45,
        item.peg <= 2.5,
        item.roi >= 10,
        item.growth >= 8,
    ]
    return round(sum(checks) / len(checks) * 100)


def _float_value(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _candidate_model_summary(ticker: str) -> dict[str, float | str | int]:
    rows: list[dict[str, float | str]] = []
    missing_samples = 0
    for strategy in STRATEGIES:
        for period_id, (start, end, weight) in MODEL_VALIDATION_PERIODS.items():
            try:
                result = run_backtest(strategy.id, ticker, start, end)
            except Exception:
                missing_samples += 1
                continue
            rows.append({
                "strategy_id": strategy.id,
                "period": period_id,
                "weight": weight,
                "annual_return": result.annual_return,
                "max_drawdown": result.max_drawdown,
            })
    if not rows:
        return {"score": 0, "best_strategy": "无真实数据", "data_quality": 0.0, "missing_samples": missing_samples}
    score_map = _ticker_validation_scores({ticker: rows}).get(ticker, {})
    return {
        "score": int(score_map.get("score", 0)),
        "best_strategy": str(score_map.get("best_strategy", "unknown")),
        "data_quality": float(score_map.get("data_quality", 0)),
        "missing_samples": missing_samples,
    }


@app.get("/portfolio/optimization")
def portfolio_optimization() -> PortfolioOptimization:
    account_total = max(_account_total(), 1)
    cash_target = round(account_total * 0.08, 2)
    suggestions: list[AllocationSuggestion] = []
    target_weights = {"NOK.US": 0.04, "NOK": 0.03, "SMR.US": 0.02, "IAU": 0.08, "NVDA": 0.02}
    for holding in HOLDINGS:
        current_weight = holding.market_value / account_total
        target_weight = target_weights.get(holding.ticker, 0.03)
        diff = round((target_weight - current_weight) * account_total, 2)
        if diff > 25:
            action = "可小额补足"
        elif diff < -25:
            action = "减仓释放现金"
        else:
            action = "维持"
        suggestions.append(
            AllocationSuggestion(
                ticker=holding.ticker,
                current_weight=round(current_weight * 100, 2),
                target_weight=round(target_weight * 100, 2),
                action=action,
                amount=abs(diff),
                reason="目标权重来自当前风控：高回撤标的降权，黄金 ETF 保留防守仓。",
            )
        )
    cash_balance = _cash_balance()
    cash_action = "现金过低，暂停新增买入" if cash_balance < cash_target else "现金充足，可按模型分批"
    return PortfolioOptimization(
        account_total=round(account_total, 2),
        cash_balance=cash_balance,
        cash_target=cash_target,
        cash_action=cash_action,
        suggestions=suggestions,
    )


@app.get("/models/validation")
def model_validation() -> list[ModelValidationItem]:
    output: list[ModelValidationItem] = []
    ticker_results: dict[str, list[dict[str, float | str]]] = {item.ticker: [] for item in WATCHLIST}
    for strategy in STRATEGIES:
        period_results: dict[str, list] = {}
        missing_samples = 0
        for period_id, (start, end, weight) in MODEL_VALIDATION_PERIODS.items():
            results = []
            for item in WATCHLIST:
                try:
                    results.append(run_backtest(strategy.id, item.ticker, start, end))
                except Exception:
                    missing_samples += 1
            period_results[period_id] = results
            for result in results:
                ticker_results.setdefault(result.ticker, []).append({
                    "strategy_id": strategy.id,
                    "period": period_id,
                    "weight": weight,
                    "annual_return": result.annual_return,
                    "max_drawdown": result.max_drawdown,
                })
        total_samples = len(WATCHLIST) * len(MODEL_VALIDATION_PERIODS)
        valid_samples = total_samples - missing_samples
        data_quality = valid_samples / max(total_samples, 1) * 100
        weighted_rows = _weighted_strategy_rows(period_results)
        if not weighted_rows:
            output.append(
                ModelValidationItem(
                    strategy_id=strategy.id,
                    tested=total_samples,
                    valid_samples=0,
                    missing_samples=missing_samples,
                    data_quality=0,
                    data_quality_label="无真实数据",
                    best_ticker="-",
                    average_annual_return=0,
                    average_max_drawdown=0,
                    tuning_note="缺少真实历史数据，本次不生成模型分。",
                )
            )
            continue
        best = max(weighted_rows, key=lambda row: row["weighted_return"])
        avg_return = sum(row["weighted_return"] for row in weighted_rows) / max(len(weighted_rows), 1)
        avg_drawdown = sum(row["weighted_drawdown"] for row in weighted_rows) / max(len(weighted_rows), 1)
        short_return, short_drawdown = _period_average(period_results["short"])
        medium_return, medium_drawdown = _period_average(period_results["medium"])
        long_return, long_drawdown = _period_average(period_results["long"])
        if long_drawdown < -35 or avg_drawdown < -28:
            note = "回撤过大，调低单票权重并提高止损敏感度。"
        elif short_return < 0 and medium_return < 0:
            note = "收益不足，减少逆势补仓，增加趋势确认。"
        elif short_return < 0:
            note = "短期转弱，保留中期信号但执行上降低追涨和补仓。"
        else:
            note = "可保留当前参数，继续扩大样本观察。"
        output.append(
            ModelValidationItem(
                strategy_id=strategy.id,
                tested=total_samples,
                valid_samples=valid_samples,
                missing_samples=missing_samples,
                data_quality=round(data_quality, 2),
                data_quality_label=_data_quality_label(data_quality),
                best_ticker=str(best["ticker"]),
                average_annual_return=round(avg_return, 2),
                average_max_drawdown=round(avg_drawdown, 2),
                short_return=round(short_return, 2),
                short_drawdown=round(short_drawdown, 2),
                medium_return=round(medium_return, 2),
                medium_drawdown=round(medium_drawdown, 2),
                long_return=round(long_return, 2),
                long_drawdown=round(long_drawdown, 2),
                tuning_note=note,
            )
        )
    MODEL_VALIDATION_BY_TICKER.clear()
    MODEL_VALIDATION_BY_TICKER.update(_ticker_validation_scores(ticker_results))
    return output


def _weighted_strategy_rows(period_results: dict[str, list]) -> list[dict[str, float | str]]:
    rows: dict[str, dict[str, float | str]] = {}
    for period_id, results in period_results.items():
        weight = MODEL_VALIDATION_PERIODS[period_id][2]
        for result in results:
            row = rows.setdefault(result.ticker, {"ticker": result.ticker, "weighted_return": 0.0, "weighted_drawdown": 0.0})
            row["weighted_return"] = float(row["weighted_return"]) + result.annual_return * weight
            row["weighted_drawdown"] = float(row["weighted_drawdown"]) + result.max_drawdown * weight
    return list(rows.values())


def _period_average(results: list) -> tuple[float, float]:
    if not results:
        return 0.0, 0.0
    avg_return = sum(result.annual_return for result in results) / len(results)
    avg_drawdown = sum(result.max_drawdown for result in results) / len(results)
    return avg_return, avg_drawdown


def _data_quality_label(data_quality: float) -> str:
    if data_quality >= 80:
        return "真实数据充足"
    if data_quality >= 50:
        return "真实数据不足，评分降权"
    if data_quality > 0:
        return "真实数据过少，仅观察"
    return "无真实数据"


def _ticker_validation_scores(ticker_results: dict[str, list[dict[str, float | str]]]) -> dict[str, dict[str, float | str]]:
    scores: dict[str, dict[str, float | str]] = {}
    for ticker, rows in ticker_results.items():
        if not rows:
            continue
        avg_return = sum(float(row["annual_return"]) * float(row["weight"]) for row in rows) / len(STRATEGIES)
        avg_drawdown = sum(float(row["max_drawdown"]) * float(row["weight"]) for row in rows) / len(STRATEGIES)
        data_quality = len(rows) / max(len(STRATEGIES) * len(MODEL_VALIDATION_PERIODS), 1) * 100
        long_drawdowns = [float(row["max_drawdown"]) for row in rows if row["period"] == "long"]
        worst_long_drawdown = min(long_drawdowns) if long_drawdowns else avg_drawdown
        best_row = max(rows, key=lambda row: float(row["annual_return"]))
        best_strategy = str(best_row["strategy_id"])
        best_return = float(best_row["annual_return"])
        drawdown_penalty = max(0, abs(worst_long_drawdown) - 30) * 0.35
        quality_penalty = 0 if data_quality >= 80 else (18 if data_quality >= 50 else 35)
        score = round(max(0, min(100, 50 + avg_return * 0.8 + avg_drawdown * 0.4 - drawdown_penalty - quality_penalty)))
        if data_quality < 50:
            score = min(score, 39)
        if score < 40:
            reason = f"{best_strategy} 最佳但多周期回撤 {avg_drawdown:.1f}%，模型分偏低，{_data_quality_label(data_quality)}"
        elif score < 55:
            reason = f"{best_strategy} 最佳，多周期年化 {avg_return:.1f}%，仍需观察，{_data_quality_label(data_quality)}"
        else:
            reason = f"{best_strategy} 最佳，多周期年化 {avg_return:.1f}%，回撤 {avg_drawdown:.1f}%，{_data_quality_label(data_quality)}"
        scores[ticker] = {
            "score": score,
            "reason": reason,
            "best_strategy": best_strategy,
            "average_annual_return": round(avg_return, 2),
            "average_max_drawdown": round(avg_drawdown, 2),
            "best_strategy_return": round(best_return, 2),
            "data_quality": round(data_quality, 2),
            "data_quality_label": _data_quality_label(data_quality),
        }
    return scores


@app.get("/signals")
def signals() -> list[Signal]:
    return [generate_signal(item) for item in dynamic_watchlist(WATCHLIST, HOLDINGS, MODEL_VALIDATION_BY_TICKER)]


@app.get("/discipline/events")
def discipline_events():
    return EVENTS


@app.post("/automation/pause")
def pause_automation() -> dict[str, bool]:
    state["automation_paused"] = True
    return {"automation_paused": True}


@app.post("/automation/resume")
def resume_automation() -> dict[str, bool]:
    state["automation_paused"] = False
    return {"automation_paused": False}


@app.get("/orders")
def orders() -> list[TradeOrder]:
    return ORDERS


@app.post("/orders")
def submit_order(request: OrderRequest) -> TradeOrder:
    decision = risk_engine().evaluate_order(request)
    if not decision.allowed:
        return TradeOrder(
            id="risk_blocked",
            broker=execution_config().mode,
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status=f"BLOCKED: {decision.blocked_reason}",
            created_at="now",
        )
    order = broker_from_env().place_order(request)
    ORDERS.insert(0, order)
    return order


@app.post("/orders/preview")
def preview_order(request: OrderRequest, target: str = Query(default="")):
    mode = target or execution_config().mode
    if mode in {"usmart-paper", "usmart-live"}:
        return USmartBrokerAdapter(live=mode == "usmart-live").prepare_order(request)
    decision = risk_engine().evaluate_order(request)
    return {
        "broker": mode,
        "ready_to_submit": decision.allowed,
        "blockers": [] if decision.allowed else [decision.blocked_reason],
        "body": request.model_dump(),
    }


@app.post("/manual-executions")
def create_manual_execution(request: ManualExecutionRequest) -> TradeOrder:
    ticker = request.ticker.strip().upper()
    order = TradeOrder(
        id=f"manual_{request.broker}_{len(ORDERS) + 1}",
        broker=request.broker,
        ticker=ticker,
        side=request.side,
        qty=request.qty,
        order_type="MANUAL",
        limit_price=request.price,
        status=f"MANUAL_RECORDED: {request.note or 'user confirmed in broker app'}",
        created_at=request.executed_at,
    )
    ORDERS.insert(0, order)
    holding_note = _apply_manual_execution_to_holdings(request, ticker)
    EVENTS.insert(
        0,
        DisciplineEvent(
            id=f"manual_event_{len(EVENTS) + 1}",
            ticker=ticker,
            title="线下交易已回填",
            reason=f"{request.broker} {request.side.value} {request.qty} 股，成交价 {request.price:.2f}。",
            action=request.note or holding_note,
            severity="ok",
            created_at=request.executed_at,
        ),
    )
    _save_local_state()
    return order


def _apply_manual_execution_to_holdings(request: ManualExecutionRequest, ticker: str) -> str:
    broker = request.broker if request.broker in {"za-bank", "usmart", "ibkr"} else "manual"
    existing = next((item for item in HOLDINGS if item.broker == broker and item.ticker == ticker), None)
    qty = float(request.qty)
    price = float(request.price)
    notional = round(qty * price, 2)
    if request.side == "BUY":
        ACCOUNT_CASH_BALANCES[broker] = round(ACCOUNT_CASH_BALANCES.get(broker, 0.0) - notional, 2)
    else:
        ACCOUNT_CASH_BALANCES[broker] = round(ACCOUNT_CASH_BALANCES.get(broker, 0.0) + notional, 2)
    if request.side == "BUY":
        if existing:
            total_qty = existing.qty + qty
            total_cost = existing.avg_cost * existing.qty + price * qty
            existing.qty = total_qty
            existing.avg_cost = round(total_cost / total_qty, 4) if total_qty else price
            existing.market_price = price
            existing.market_value = round(total_qty * price, 2)
            existing.pnl = round((price - existing.avg_cost) * total_qty, 2)
            existing.updated_at = request.executed_at
            _refresh_holding_quote(existing)
            return "已更新本地持仓成本和数量。"
        holding = Holding(
            broker=broker,
            ticker=ticker,
            qty=qty,
            avg_cost=price,
            market_price=price,
            market_value=round(qty * price, 2),
            pnl=0,
            updated_at=request.executed_at,
        )
        _refresh_holding_quote(holding)
        HOLDINGS.append(holding)
        return "已新增本地持仓。"

    if not existing:
        return "未找到对应持仓，仅记录线下卖出动作。"
    remaining_qty = max(existing.qty - qty, 0)
    if remaining_qty <= 0:
        HOLDINGS.remove(existing)
        return "卖出后本地持仓已清零。"
    existing.qty = remaining_qty
    existing.market_price = price
    existing.market_value = round(remaining_qty * price, 2)
    existing.pnl = round((price - existing.avg_cost) * remaining_qty, 2)
    existing.updated_at = request.executed_at
    _refresh_holding_quote(existing)
    return "已扣减本地持仓数量。"


def _refresh_holding_quote(holding: Holding) -> bool:
    try:
        quotes = market_quotes([holding.ticker])
    except Exception:
        return False
    quote = quotes[0] if quotes else None
    if not quote or quote.price <= 0:
        return False
    holding.market_price = quote.price
    holding.market_value = round(holding.qty * quote.price, 2)
    holding.pnl = round((quote.price - holding.avg_cost) * holding.qty, 2)
    holding.updated_at = quote.updated_at
    save_quotes([quote])
    return True


@app.post("/imports/broker-records")
def import_broker_records(request: BrokerImportRequest) -> BrokerImportResult:
    holdings_updated = 0
    trades_recorded = 0
    for record in request.records:
        if record.record_type == "holding":
            existing = next((item for item in HOLDINGS if item.broker == record.broker and item.ticker == record.ticker), None)
            market_value = record.qty * record.price
            if existing:
                existing.qty = record.qty
                existing.avg_cost = record.price
                existing.market_price = record.price
                existing.market_value = market_value
                existing.pnl = 0
                existing.updated_at = record.executed_at
            else:
                HOLDINGS.append(
                    Holding(
                        broker=record.broker if record.broker in {"za-bank", "usmart", "ibkr"} else "manual",
                        ticker=record.ticker,
                        qty=record.qty,
                        avg_cost=record.price,
                        market_price=record.price,
                        market_value=market_value,
                        pnl=0,
                        updated_at=record.executed_at,
                    )
                )
            holdings_updated += 1
        else:
            ORDERS.insert(
                0,
                TradeOrder(
                    id=f"import_{record.broker}_{len(ORDERS) + 1}",
                    broker=record.broker,
                    ticker=record.ticker,
                    side=record.side or "BUY",
                    qty=int(record.qty),
                    order_type="IMPORT",
                    limit_price=record.price,
                    status=f"IMPORTED: {record.note or 'broker record'}",
                    created_at=record.executed_at,
                ),
            )
            trades_recorded += 1
    _save_local_state()
    return BrokerImportResult(
        imported=len(request.records),
        holdings_updated=holdings_updated,
        trades_recorded=trades_recorded,
        message="导入完成，已更新本地持仓和交易记录。",
    )


@app.post("/imports/usmart-screenshot")
def import_usmart_screenshot(request: USmartScreenshotImportRequest) -> USmartScreenshotImportResult:
    net_asset, parsed_holdings, warnings = parse_usmart_portfolio_screenshot(
        image_path=request.image_path,
        extracted_text=request.extracted_text,
        as_of=request.as_of,
        broker=request.broker,
    )
    for parsed in parsed_holdings:
        existing = next((item for item in HOLDINGS if item.broker == parsed.broker and item.ticker == parsed.ticker), None)
        if existing:
            existing.qty = parsed.qty
            existing.avg_cost = parsed.avg_cost
            existing.market_price = parsed.market_price
            existing.market_value = parsed.market_value
            existing.pnl = parsed.pnl
            existing.updated_at = parsed.updated_at
        else:
            HOLDINGS.append(parsed)
    if net_asset > 0:
        holding_value = sum(item.market_value for item in parsed_holdings)
        ACCOUNT_CASH_BALANCES[request.broker] = round(max(net_asset - holding_value, 0), 2)
    _save_local_state()
    return USmartScreenshotImportResult(
        broker=request.broker,
        image_path=request.image_path,
        net_asset=net_asset,
        imported_holdings=len(parsed_holdings),
        warnings=warnings,
        holdings=parsed_holdings,
    )


@app.post("/imports/za-screenshot")
def import_za_screenshot(request: ZABankScreenshotImportRequest) -> ZABankScreenshotImportResult:
    parsed_holdings, warnings = parse_za_bank_portfolio_screenshot(
        image_path=request.image_path,
        extracted_text=request.extracted_text,
        as_of=request.as_of,
    )
    for parsed in parsed_holdings:
        existing = next((item for item in HOLDINGS if item.broker == parsed.broker and item.ticker == parsed.ticker), None)
        if existing:
            existing.qty = parsed.qty
            existing.avg_cost = parsed.avg_cost
            existing.market_price = parsed.market_price
            existing.market_value = parsed.market_value
            existing.pnl = parsed.pnl
            existing.updated_at = parsed.updated_at
        else:
            HOLDINGS.append(parsed)
    _save_local_state()
    return ZABankScreenshotImportResult(
        image_path=request.image_path,
        imported_holdings=len(parsed_holdings),
        warnings=warnings,
        holdings=parsed_holdings,
    )


@app.get("/risk/status")
def risk_status():
    return risk_engine().status()


@app.get("/execution/config")
def get_execution_config():
    return execution_config()


@app.get("/brokers/capabilities")
def get_broker_capabilities():
    return broker_capabilities()


def _account_total() -> float:
    return round(sum(holding.market_value for holding in HOLDINGS) + _cash_balance(), 2)


def _cash_balance() -> float:
    return round(sum(ACCOUNT_CASH_BALANCES.values()), 2)


def _dashboard_pnl() -> float:
    if state["quote_snapshot"]:
        return round(sum(holding.pnl for holding in HOLDINGS), 2)
    return -21.72
