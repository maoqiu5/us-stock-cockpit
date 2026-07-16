from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .broker import USmartBrokerAdapter, broker_capabilities, broker_from_env, execution_config
from .data_sources import data_source_statuses, market_quotes
from .historical_prices import is_us_market_open, previous_close_quotes, validate_yahoo_ticker
from .models import AddWatchlistRequest, AllocationSuggestion, BacktestRequest, BrokerImportRequest, BrokerImportResult, CandidateStock, DisciplineEvent, Holding, HoldingAdvice, ManualExecutionRequest, ModelValidationItem, OrderRequest, PortfolioOptimization, PreviousCloseImportResult, Signal, TradeOrder, USmartScreenshotImportRequest, USmartScreenshotImportResult, ValidateTickerResult, WatchlistItem, ZABankScreenshotImportRequest, ZABankScreenshotImportResult
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


@app.post("/watchlist")
def add_watchlist_item(request: AddWatchlistRequest) -> WatchlistItem:
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
    normalized = ticker.strip().upper()
    holding_tickers = {holding.ticker for holding in HOLDINGS}
    if normalized in holding_tickers:
        raise HTTPException(status_code=400, detail="当前持仓股票不能从股票池删除，请先在持仓纪律里处理。")
    before = len(WATCHLIST)
    WATCHLIST[:] = [item for item in WATCHLIST if item.ticker != normalized]
    if len(WATCHLIST) == before:
        raise HTTPException(status_code=404, detail="ticker not found")
    return {"deleted": normalized}


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


@app.get("/advice/holdings")
def holding_advice() -> list[HoldingAdvice]:
    account_total = max(_account_total(), 1)
    advice: list[HoldingAdvice] = []
    for holding in HOLDINGS:
        cost_basis = max(holding.avg_cost * holding.qty, 0.01)
        pnl_pct = holding.pnl / cost_basis * 100
        current_weight = holding.market_value / account_total
        if pnl_pct <= -35:
            action = "减仓/禁止补仓"
            risk_level = "high"
            confidence = 0.82
            target = min(current_weight, 0.03)
            reason = f"持仓亏损 {pnl_pct:.1f}%，已超过纪律线，先控制单票风险。"
        elif pnl_pct <= -15:
            action = "持有观察"
            risk_level = "medium"
            confidence = 0.68
            target = min(current_weight, 0.05)
            reason = f"持仓亏损 {pnl_pct:.1f}%，等待模型转强或止损条件确认。"
        elif current_weight > 0.12:
            action = "降低集中度"
            risk_level = "medium"
            confidence = 0.64
            target = 0.08
            reason = f"当前权重 {current_weight * 100:.1f}%，超过单票观察上限。"
        else:
            action = "继续跟踪"
            risk_level = "low"
            confidence = 0.55
            target = max(current_weight, 0.02)
            reason = "未触发强制卖出条件，继续用模型信号跟踪。"
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


@app.get("/screening/candidates")
def screening_candidates() -> list[CandidateStock]:
    existing = {item.ticker.replace(".US", "") for item in WATCHLIST}
    candidates = [
        CandidateStock(ticker="MSFT", name="Microsoft", sector="Software", score=86, reason="盈利质量稳定，适合作为大盘科技核心观察。", action="加入监控"),
        CandidateStock(ticker="GOOGL", name="Alphabet", sector="Communication", score=84, reason="估值与现金流相对均衡，适合 PE/ROI 双模型跟踪。", action="加入监控"),
        CandidateStock(ticker="AMZN", name="Amazon", sector="Consumer/Cloud", score=79, reason="增长和趋势因子较强，适合 PEG_v1 观察。", action="观察等待"),
        CandidateStock(ticker="QQQ", name="Nasdaq 100 ETF", sector="ETF", score=76, reason="可作为科技仓位基准和现金替代观察。", action="加入监控"),
        CandidateStock(ticker="SPY", name="S&P 500 ETF", sector="ETF", score=72, reason="用于基准、风险对冲和组合回撤参照。", action="加入监控"),
    ]
    return [candidate for candidate in candidates if candidate.ticker not in existing]


@app.get("/portfolio/optimization")
def portfolio_optimization() -> PortfolioOptimization:
    account_total = max(_account_total(), 1)
    cash_target = round(account_total * 0.12, 2)
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
    cash_action = "现金过低，暂停新增买入" if CASH_BALANCE < cash_target else "现金充足，可按模型分批"
    return PortfolioOptimization(
        account_total=round(account_total, 2),
        cash_balance=CASH_BALANCE,
        cash_target=cash_target,
        cash_action=cash_action,
        suggestions=suggestions,
    )


@app.get("/models/validation")
def model_validation() -> list[ModelValidationItem]:
    output: list[ModelValidationItem] = []
    for strategy in STRATEGIES:
        results = [run_backtest(strategy.id, item.ticker, "2026-05-01", "2026-07-16") for item in WATCHLIST]
        best = max(results, key=lambda result: result.annual_return)
        avg_return = sum(result.annual_return for result in results) / max(len(results), 1)
        avg_drawdown = sum(result.max_drawdown for result in results) / max(len(results), 1)
        if avg_drawdown < -35:
            note = "回撤过大，调低单票权重并提高止损敏感度。"
        elif avg_return < 0:
            note = "收益不足，减少逆势补仓，增加趋势确认。"
        else:
            note = "可保留当前参数，继续扩大样本观察。"
        output.append(
            ModelValidationItem(
                strategy_id=strategy.id,
                tested=len(results),
                best_ticker=best.ticker,
                average_annual_return=round(avg_return, 2),
                average_max_drawdown=round(avg_drawdown, 2),
                tuning_note=note,
            )
        )
    return output


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
