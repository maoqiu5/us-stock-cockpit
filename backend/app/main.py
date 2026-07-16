from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .broker import USmartBrokerAdapter, broker_capabilities, broker_from_env, execution_config
from .models import BacktestRequest, ManualExecutionRequest, OrderRequest, Signal, TradeOrder
from .risk import RiskConfig, RiskEngine
from .seed import EVENTS, ORDERS, STRATEGIES, WATCHLIST
from .strategy import generate_signal, run_backtest

app = FastAPI(title="美股驾驶舱 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = {"automation_paused": False}


def risk_engine() -> RiskEngine:
    return RiskEngine(RiskConfig(automation_paused=state["automation_paused"]))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard/summary")
def dashboard_summary() -> dict:
    return {
        "account_total": 284350,
        "today_pnl": 12480,
        "discipline_score": 86,
        "active_signals": 9,
        "signal_breakdown": {"buy": 2, "sell": 2, "hold": 3, "watch": 4},
        "max_drawdown": -8.4,
        "max_drawdown_limit": -12,
        "execution_mode": "本地记录" if execution_config().mode == "paper" else execution_config().mode,
        "automation_paused": state["automation_paused"],
        "global_risk": "暂停" if state["automation_paused"] else "正常",
        "data_source": "本地记录",
        "sync_status": "未登录",
        "local_saved_at": "07/06 14:51",
        "today_orders": "0 / 5",
        "workflow": [
            {"step": 1, "title": "建模型", "detail": "4 个模型", "status": "done"},
            {"step": 2, "title": "筛股票", "detail": "10 个判定", "status": "done"},
            {"step": 3, "title": "刷行情", "detail": "今日 07/06 14:51", "status": "done"},
            {"step": 4, "title": "看信号", "detail": "9 条信号", "status": "active"},
            {"step": 5, "title": "记执行", "detail": "3 条记录", "status": "active"},
        ],
        "checks": [
            {"severity": "ok", "title": "行情已准备好", "detail": "今天已刷新 3 只股票，可以继续看信号。", "time": "07/06 14:51"},
            {"severity": "risk", "title": "NVDA 出现风险提醒", "detail": "PE 52.1 > 40，已触发卖出/减仓候选，请按风控处理。", "time": "自定义 PE 纪律策略 · 优先级 100"},
        ],
    }


@app.get("/strategies")
def strategies():
    return STRATEGIES


@app.post("/strategies/{strategy_id}/backtest")
def backtest(strategy_id: str, request: BacktestRequest):
    if strategy_id not in {strategy.id for strategy in STRATEGIES}:
        raise HTTPException(status_code=404, detail="strategy not found")
    return run_backtest(strategy_id, request.ticker)


@app.get("/watchlist")
def watchlist():
    return WATCHLIST


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


@app.get("/risk/status")
def risk_status():
    return risk_engine().status()


@app.get("/execution/config")
def get_execution_config():
    return execution_config()


@app.get("/brokers/capabilities")
def get_broker_capabilities():
    return broker_capabilities()
