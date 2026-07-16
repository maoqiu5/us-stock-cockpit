from backend.app.models import OrderRequest, Side
from backend.app.risk import RiskConfig, RiskEngine
from backend.app.seed import WATCHLIST
from backend.app.strategy import generate_signal, run_backtest, score_watchlist_item


def test_factor_score_and_signal_for_meta():
    meta = next(item for item in WATCHLIST if item.ticker == "META")
    assert score_watchlist_item(meta) >= 80
    signal = generate_signal(meta)
    assert signal.side == Side.buy
    assert signal.confidence >= 0.8


def test_overheated_nvda_generates_sell_signal():
    nvda = next(item for item in WATCHLIST if item.ticker == "NVDA")
    signal = generate_signal(nvda)
    assert signal.side == Side.sell
    assert "估值过热" in signal.reason


def test_backtest_returns_expected_shape():
    result = run_backtest("pe_v1", "META")
    assert result.annual_return == 30.67
    assert result.pnl == 48308
    assert result.trades == 13
    assert len(result.records) == 7


def test_risk_blocks_single_position_limit():
    engine = RiskEngine(RiskConfig(account_value=100000))
    request = OrderRequest(ticker="META", side=Side.buy, qty=20, limit_price=1000)
    decision = engine.evaluate_order(request)
    assert not decision.allowed
    assert "单票" in decision.blocked_reason


def test_risk_blocks_when_automation_paused():
    engine = RiskEngine(RiskConfig(automation_paused=True))
    request = OrderRequest(ticker="META", side=Side.buy, qty=1, limit_price=100)
    decision = engine.evaluate_order(request)
    assert not decision.allowed
    assert "暂停" in decision.blocked_reason
