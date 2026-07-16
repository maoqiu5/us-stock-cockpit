from __future__ import annotations

from .models import DisciplineEvent, Holding, OrderRequest, Side, StrategyModel, TradeOrder, WatchlistItem

PORTFOLIO_UNIVERSE = ["NOK.US", "SMR.US", "NOK", "IAU", "NVDA"]

STRATEGIES = [
    StrategyModel(
        id="pe_v1",
        name="PE_v1",
        factor_set=["PE", "PEG", "ROI", "drawdown_guard"],
        universe=PORTFOLIO_UNIVERSE,
        status="运行中",
        score=58,
        annual_return=6.8,
        max_drawdown=-56.53,
        trades=5,
        description="估值纪律策略：当前先服务真实持仓对账，对 NOK/SMR/IAU/NVDA 做估值、趋势和回撤纪律提醒。",
        backtest_config={"start": "2026-05-01", "end": "2026-07-16", "benchmark": "SPY"},
    ),
    StrategyModel(
        id="peg_v1",
        name="PEG_v1",
        factor_set=["PEG", "revenue_growth", "gross_margin", "momentum"],
        universe=PORTFOLIO_UNIVERSE,
        status="运行中",
        score=52,
        annual_return=4.2,
        max_drawdown=-56.53,
        trades=5,
        description="成长估值策略：重点识别 SMR/NVDA 这类高波动标的是否仍满足增长质量和趋势纪律。",
        backtest_config={"start": "2026-05-01", "end": "2026-07-16", "benchmark": "QQQ"},
    ),
    StrategyModel(
        id="roi_v1",
        name="ROI_v1",
        factor_set=["ROI", "free_cash_flow", "capex_pressure", "trend"],
        universe=PORTFOLIO_UNIVERSE,
        status="实盘预留",
        score=49,
        annual_return=3.7,
        max_drawdown=-30.12,
        trades=3,
        description="资本效率策略：先用于当前小额持仓的卖出条件、补仓禁令和资金占用纪律记录。",
        backtest_config={"start": "2026-05-01", "end": "2026-07-16", "benchmark": "SPY"},
    ),
]

WATCHLIST = [
    WatchlistItem(ticker="NOK.US", name="Nokia Corp · uSMART", sector="Communication Equipment", pe=18.2, peg=1.9, roi=8.6, growth=1.8, trend="下行", eligible=False, signal="RISK"),
    WatchlistItem(ticker="SMR.US", name="NuScale Power · uSMART", sector="Energy Technology", pe=88.0, peg=4.8, roi=-18.5, growth=24.0, trend="下行", eligible=False, signal="RISK"),
    WatchlistItem(ticker="NOK", name="Nokia Corp · ZA Bank", sector="Communication Equipment", pe=18.2, peg=1.9, roi=8.6, growth=1.8, trend="下行", eligible=False, signal="RISK"),
    WatchlistItem(ticker="IAU", name="iShares Gold Trust ETF · ZA Bank", sector="ETF", pe=0.0, peg=0.0, roi=0.0, growth=0.0, trend="横盘", eligible=False, signal="WATCH"),
    WatchlistItem(ticker="NVDA", name="NVIDIA Corp · ZA Bank", sector="Semiconductors", pe=52.1, peg=1.95, roi=44.2, growth=61.0, trend="过热", eligible=False, signal="RISK"),
]

EVENTS = [
    DisciplineEvent(
        id="evt_001",
        ticker="PORTFOLIO",
        title="ZA/uSMART 持仓已导入",
        reason="已从两张截图同步 5 条真实持仓，当前账户总市值约 $2,736.95。",
        action="先做本地对账和风险观察",
        severity="ok",
        created_at="07/16 14:04",
    ),
    DisciplineEvent(
        id="evt_002",
        ticker="SMR.US",
        title="SMR.US 回撤较大",
        reason="uSMART 持仓盈亏 -$869.60 / -56.53%，已超过纪律观察线。",
        action="阻断新增买入，等待人工确认卖出条件",
        severity="risk",
        created_at="07/16 14:02",
    ),
    DisciplineEvent(
        id="evt_003",
        ticker="NOK",
        title="NOK 双账户持仓",
        reason="ZA Bank 44 股、uSMART 99 股，合计 143 股，合并持仓亏损约 -$686.12。",
        action="先合并看仓位，不自动补仓",
        severity="warn",
        created_at="07/16 14:04",
    ),
]

ORDERS = [
    TradeOrder(id="imp_usmart_001", broker="usmart", ticker="NOK.US", side=Side.buy, qty=99, order_type="IMPORT", limit_price=11.23, status="IMPORTED_HOLDING", created_at="07/16 14:02"),
    TradeOrder(id="imp_usmart_002", broker="usmart", ticker="SMR.US", side=Side.buy, qty=80, order_type="IMPORT", limit_price=8.36, status="IMPORTED_HOLDING", created_at="07/16 14:02"),
    TradeOrder(id="imp_za_001", broker="za-bank", ticker="NOK", side=Side.buy, qty=44, order_type="IMPORT", limit_price=11.25, status="IMPORTED_HOLDING", created_at="07/16 14:04"),
    TradeOrder(id="imp_za_002", broker="za-bank", ticker="IAU", side=Side.buy, qty=6, order_type="IMPORT", limit_price=76.28, status="IMPORTED_HOLDING", created_at="07/16 14:04"),
    TradeOrder(id="imp_za_003", broker="za-bank", ticker="NVDA", side=Side.buy, qty=1, order_type="IMPORT", limit_price=212.5, status="IMPORTED_FRACTIONAL_0.0005", created_at="07/16 14:04"),
]

HOLDINGS = [
    Holding(
        broker="usmart",
        ticker="NOK.US",
        qty=99,
        avg_cost=16.005,
        market_price=11.23,
        market_value=1111.77,
        pnl=-472.72,
        updated_at="07/16 14:02",
    ),
    Holding(
        broker="usmart",
        ticker="SMR.US",
        qty=80,
        avg_cost=19.23,
        market_price=8.36,
        market_value=668.80,
        pnl=-869.60,
        updated_at="07/16 14:02",
    ),
    Holding(
        broker="za-bank",
        ticker="NOK",
        qty=44,
        avg_cost=16.10,
        market_price=11.25,
        market_value=495.00,
        pnl=-213.40,
        updated_at="07/16 14:04",
    ),
    Holding(
        broker="za-bank",
        ticker="IAU",
        qty=6,
        avg_cost=85.65,
        market_price=76.28,
        market_value=457.68,
        pnl=-56.22,
        updated_at="07/16 14:04",
    ),
    Holding(
        broker="za-bank",
        ticker="NVDA",
        qty=0.0005,
        avg_cost=220.0,
        market_price=212.5,
        market_value=0.11,
        pnl=-0.01,
        updated_at="07/16 14:04",
    ),
]

SAMPLE_REQUEST = OrderRequest(ticker="NOK.US", side=Side.buy, qty=1, limit_price=11.23)
