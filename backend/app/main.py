from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .broker import USmartBrokerAdapter, broker_capabilities, broker_from_env, execution_config
from .data_sources import data_source_statuses, market_quotes
from .historical_prices import previous_close_quotes
from .models import BacktestRequest, BrokerImportRequest, BrokerImportResult, DisciplineEvent, Holding, ManualExecutionRequest, OrderRequest, PreviousCloseImportResult, Signal, TradeOrder, USmartScreenshotImportRequest, USmartScreenshotImportResult, ZABankScreenshotImportRequest, ZABankScreenshotImportResult
from .risk import RiskConfig, RiskEngine
from .seed import EVENTS, HOLDINGS, ORDERS, STRATEGIES, WATCHLIST
from .strategy import generate_signal, run_backtest
from .usmart_importer import parse_usmart_portfolio_screenshot
from .za_importer import parse_za_bank_portfolio_screenshot

app = FastAPI(title="美股驾驶舱 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CASH_BALANCE = 3.59

state = {
    "automation_paused": False,
    "quote_snapshot": None,
    "quote_snapshot_source": "",
    "quote_snapshot_as_of": "",
}


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
    return run_backtest(strategy_id, request.ticker, request.start_date, request.end_date)


@app.get("/watchlist")
def watchlist():
    return WATCHLIST


@app.get("/market/quotes")
def quotes(symbols: str = Query(default="")):
    requested = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if state["quote_snapshot"]:
        cached = {quote.ticker: quote for quote in state["quote_snapshot"]}
        wanted = requested or [item.ticker for item in WATCHLIST]
        return [cached[ticker] for ticker in wanted if ticker in cached]
    return market_quotes(requested or [item.ticker for item in WATCHLIST])


@app.post("/market/import-previous-close")
def import_previous_close() -> PreviousCloseImportResult:
    tickers = list(dict.fromkeys(holding.ticker for holding in HOLDINGS))
    quotes, warnings = previous_close_quotes(tickers)
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


@app.get("/portfolio/holdings")
def holdings() -> list[Holding]:
    return HOLDINGS


@app.get("/signals")
def signals() -> list[Signal]:
    return [generate_signal(item) for item in WATCHLIST]


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
    order = TradeOrder(
        id=f"manual_{request.broker}_{len(ORDERS) + 1}",
        broker=request.broker,
        ticker=request.ticker,
        side=request.side,
        qty=request.qty,
        order_type="MANUAL",
        limit_price=request.price,
        status=f"MANUAL_RECORDED: {request.note or 'user confirmed in broker app'}",
        created_at=request.executed_at,
    )
    ORDERS.insert(0, order)
    return order


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
    return round(sum(holding.market_value for holding in HOLDINGS) + CASH_BALANCE, 2)


def _dashboard_pnl() -> float:
    if state["quote_snapshot"]:
        return round(sum(holding.pnl for holding in HOLDINGS), 2)
    return -21.72
