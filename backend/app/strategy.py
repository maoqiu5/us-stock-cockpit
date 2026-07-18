from __future__ import annotations

from dataclasses import dataclass
from math import prod
from statistics import mean

from .models import BacktestPoint, BacktestResult, Side, Signal, WatchlistItem
from .historical_prices import daily_close_series


@dataclass(frozen=True)
class FactorThresholds:
    max_pe: float = 40
    max_peg: float = 2.0
    min_roi: float = 15
    min_growth: float = 8


def score_watchlist_item(item: WatchlistItem, thresholds: FactorThresholds = FactorThresholds()) -> int:
    checks = [
        item.pe <= thresholds.max_pe,
        item.peg <= thresholds.max_peg,
        item.roi >= thresholds.min_roi,
        item.growth >= thresholds.min_growth,
        item.trend in {"上行", "横盘"},
    ]
    return round(sum(checks) / len(checks) * 100)


def generate_signal(item: WatchlistItem, strategy_id: str = "pe_v1") -> Signal:
    score = score_watchlist_item(item)
    if item.pe > 45 or item.peg > 2.6:
        return Signal(
            ticker=item.ticker,
            strategy_id=strategy_id,
            side=Side.sell,
            confidence=0.72,
            reason=f"{item.ticker} 估值过热，PE {item.pe} / PEG {item.peg} 触发减仓纪律。",
            expires_at="2026-07-07T20:00:00Z",
        )
    if score >= 80 and item.eligible:
        return Signal(
            ticker=item.ticker,
            strategy_id=strategy_id,
            side=Side.buy,
            confidence=min(0.92, score / 100),
            reason=f"{item.ticker} 因子评分 {score}，PE/PEG/ROI/增长均通过纪律线。",
            expires_at="2026-07-07T20:00:00Z",
        )
    return Signal(
        ticker=item.ticker,
        strategy_id=strategy_id,
        side=Side.buy,
        confidence=0.42,
        reason=f"{item.ticker} 暂未满足自动执行阈值，仅保留观察。",
        expires_at="2026-07-07T20:00:00Z",
    )


def run_backtest(strategy_id: str, ticker: str, start_date: str = "2026-05-01", end_date: str = "2026-07-16") -> BacktestResult:
    return _run_historical_backtest(strategy_id, ticker, start_date, end_date)


def _run_historical_backtest(strategy_id: str, ticker: str, start_date: str, end_date: str) -> BacktestResult:
    prices = daily_close_series(ticker, start_date, end_date)
    benchmark_prices = daily_close_series("SPY", start_date, end_date)
    returns = _daily_returns(prices)
    benchmark_returns = _daily_returns(benchmark_prices)
    strategy_returns = _apply_strategy(strategy_id, returns)

    equity_curve = _equity_curve(strategy_returns)
    benchmark_curve = _equity_curve(benchmark_returns)
    records = _sample_records(prices[1:], equity_curve, benchmark_curve)
    win_rate, profit_factor = _trade_stats(strategy_returns)
    annual_return = _annualized_return(equity_curve[-1] / equity_curve[0] - 1, len(strategy_returns))
    benchmark_return = _annualized_return(benchmark_curve[-1] / benchmark_curve[0] - 1, len(benchmark_returns))

    return BacktestResult(
        strategy_id=strategy_id,
        ticker=ticker,
        annual_return=round(annual_return, 2),
        pnl=round(equity_curve[-1] - 100000, 2),
        win_rate=round(win_rate, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown=round(_max_drawdown(equity_curve), 2),
        trades=_count_trades(strategy_returns),
        benchmark_return=round(benchmark_return, 2),
        records=records,
    )


def _daily_returns(prices: list[tuple[str, float]]) -> list[tuple[str, float]]:
    return [
        (prices[index][0], prices[index][1] / prices[index - 1][1] - 1)
        for index in range(1, len(prices))
        if prices[index - 1][1] > 0
    ]


def _apply_strategy(strategy_id: str, returns: list[tuple[str, float]]) -> list[tuple[str, float]]:
    adjusted: list[tuple[str, float]] = []
    peak = 1.0
    equity = 1.0
    for index, (date, raw_return) in enumerate(returns):
        recent = [value for _, value in returns[max(0, index - 5):index]]
        momentum = prod(1 + value for value in recent) - 1 if recent else 0
        if strategy_id == "pe_v1":
            drawdown = equity / peak - 1
            exposure = 0.25 if drawdown <= -0.12 else 0.85
        elif strategy_id == "peg_v1":
            exposure = 0.95 if momentum > 0 else 0.35
        elif strategy_id == "roi_v1":
            exposure = 0.65 if raw_return < -0.03 else 0.75
        else:
            exposure = 0.5
        strategy_return = raw_return * exposure
        equity *= 1 + strategy_return
        peak = max(peak, equity)
        adjusted.append((date, strategy_return))
    return adjusted


def _equity_curve(returns: list[tuple[str, float]]) -> list[float]:
    equity = 100000.0
    curve = [equity]
    for _, daily_return in returns:
        equity *= 1 + daily_return
        curve.append(round(equity, 2))
    return curve


def _sample_records(price_dates: list[tuple[str, float]], equity_curve: list[float], benchmark_curve: list[float]) -> list[BacktestPoint]:
    if not price_dates:
        return []
    max_index = min(len(price_dates), len(equity_curve) - 1, len(benchmark_curve) - 1)
    if max_index <= 7:
        indices = list(range(1, max_index + 1))
    else:
        indices = sorted({1 + round(index * (max_index - 1) / 6) for index in range(7)})
    return [
        BacktestPoint(date=price_dates[index - 1][0], equity=round(equity_curve[index], 2), benchmark=round(benchmark_curve[index], 2))
        for index in indices
    ]


def _trade_stats(returns: list[tuple[str, float]]) -> tuple[float, float]:
    wins = [value for _, value in returns if value > 0]
    losses = [abs(value) for _, value in returns if value < 0]
    win_rate = len(wins) / max(len(returns), 1)
    profit_factor = sum(wins) / max(sum(losses), 0.0001)
    return win_rate, min(profit_factor, 9.99)


def _annualized_return(total_return: float, periods: int) -> float:
    if periods <= 0:
        return 0.0
    return ((1 + total_return) ** (252 / periods) - 1) * 100


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return worst * 100


def _count_trades(returns: list[tuple[str, float]]) -> int:
    active_days = sum(1 for _, value in returns if abs(value) > 0.0001)
    return max(1, round(active_days / 8))


def average_factor_score(items: list[WatchlistItem]) -> float:
    return mean(score_watchlist_item(item) for item in items)
