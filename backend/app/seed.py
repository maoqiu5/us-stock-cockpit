from __future__ import annotations

from .models import DisciplineEvent, OrderRequest, Side, StrategyModel, TradeOrder, WatchlistItem

MAG7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]

STRATEGIES = [
    StrategyModel(
        id="pe_v1",
        name="PE_v1",
        factor_set=["PE", "PEG", "ROI", "drawdown_guard"],
        universe=MAG7,
        status="运行中",
        score=91,
        annual_return=28.4,
        max_drawdown=-12.74,
        trades=13,
        description="估值纪律策略：低于自身估值分位并且盈利质量保持时允许建仓，估值修复或风控触发后退出。",
        backtest_config={"start": "2026-05-01", "end": "2026-06-22", "benchmark": "SPY"},
    ),
    StrategyModel(
        id="peg_v1",
        name="PEG_v1",
        factor_set=["PEG", "revenue_growth", "gross_margin", "momentum"],
        universe=MAG7,
        status="运行中",
        score=86,
        annual_return=22.9,
        max_drawdown=-10.3,
        trades=9,
        description="成长估值策略：PEG 与增长质量同时满足阈值，避免只因估值低而买入增长衰减标的。",
        backtest_config={"start": "2026-05-01", "end": "2026-06-22", "benchmark": "QQQ"},
    ),
    StrategyModel(
        id="roi_v1",
        name="ROI_v1",
        factor_set=["ROI", "free_cash_flow", "capex_pressure", "trend"],
        universe=MAG7,
        status="实盘预留",
        score=82,
        annual_return=18.7,
        max_drawdown=-8.4,
        trades=7,
        description="资本效率策略：关注 ROI、自由现金流和资本开支压力，适合 AI 硬件周期的纪律化观察。",
        backtest_config={"start": "2026-05-01", "end": "2026-06-22", "benchmark": "SPY"},
    ),
]

WATCHLIST = [
    WatchlistItem(ticker="META", name="Meta Platforms Inc", sector="Communication", pe=26.1, peg=1.28, roi=31.5, growth=18.4, trend="上行", eligible=True, signal="BUY"),
    WatchlistItem(ticker="NVDA", name="NVIDIA Corp", sector="Semiconductors", pe=52.1, peg=1.95, roi=44.2, growth=61.0, trend="过热", eligible=False, signal="RISK"),
    WatchlistItem(ticker="MSFT", name="Microsoft Corp", sector="Software", pe=34.4, peg=2.07, roi=29.8, growth=15.1, trend="上行", eligible=True, signal="HOLD"),
    WatchlistItem(ticker="AAPL", name="Apple Inc", sector="Hardware", pe=31.2, peg=2.42, roi=26.0, growth=5.5, trend="横盘", eligible=False, signal="WATCH"),
    WatchlistItem(ticker="AMZN", name="Amazon.com Inc", sector="Consumer", pe=38.5, peg=1.63, roi=17.8, growth=12.0, trend="上行", eligible=True, signal="BUY"),
    WatchlistItem(ticker="GOOGL", name="Alphabet Inc", sector="Communication", pe=24.7, peg=1.19, roi=28.4, growth=13.8, trend="上行", eligible=True, signal="HOLD"),
    WatchlistItem(ticker="TSLA", name="Tesla Inc", sector="Auto", pe=68.9, peg=3.14, roi=10.2, growth=-2.1, trend="震荡", eligible=False, signal="WATCH"),
]

EVENTS = [
    DisciplineEvent(
        id="evt_001",
        ticker="META",
        title="行情已准备好",
        reason="今天已刷新 3 只股票，可以继续看信号。",
        action="允许 PE_v1 继续观察",
        severity="ok",
        created_at="07/06 14:51",
    ),
    DisciplineEvent(
        id="evt_002",
        ticker="NVDA",
        title="出现风险提醒",
        reason="PE 52.1 > 40，已触发卖出/减仓候选，请按风控处理。",
        action="阻断新增买入",
        severity="risk",
        created_at="07/06 14:51",
    ),
    DisciplineEvent(
        id="evt_003",
        ticker="AMZN",
        title="买入候选",
        reason="PEG 降至 1.63，收入增长和趋势因子通过。",
        action="等待限价单确认",
        severity="warn",
        created_at="07/06 14:52",
    ),
]

ORDERS = [
    TradeOrder(id="ord_001", broker="paper", ticker="META", side=Side.buy, qty=8, order_type="LMT", limit_price=712.4, status="FILLED", created_at="07/02 22:35"),
    TradeOrder(id="ord_002", broker="paper", ticker="NVDA", side=Side.sell, qty=12, order_type="LMT", limit_price=164.8, status="RISK_REVIEW", created_at="07/06 14:53"),
    TradeOrder(id="ord_003", broker="paper", ticker="AMZN", side=Side.buy, qty=10, order_type="LMT", limit_price=226.2, status="PENDING", created_at="07/06 14:55"),
]

SAMPLE_REQUEST = OrderRequest(ticker="META", side=Side.buy, qty=1, limit_price=712.4)
