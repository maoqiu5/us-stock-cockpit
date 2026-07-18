from backend.app.models import OrderRequest, Side
import backend.app.main as main_module
from backend.app.broker import USmartBrokerAdapter
import backend.app.data_sources as data_sources_module
import backend.app.gold_monitor as gold_monitor_module
from backend.app.data_sources import market_quotes
from backend.app.gold_monitor import gold_monitor_snapshot
from backend.app.main import import_broker_records
from backend.app.models import AddWatchlistRequest, BrokerImportRecord, BrokerImportRequest, GoldManualTradeRequest, MarketQuote
from backend.app.usmart_importer import parse_usmart_portfolio_screenshot
from backend.app.za_importer import parse_za_bank_portfolio_screenshot
from backend.app.risk import RiskConfig, RiskEngine
from backend.app.seed import WATCHLIST
import backend.app.strategy as strategy_module
from backend.app.strategy import generate_signal, run_backtest, score_watchlist_item


def test_factor_score_and_signal_for_current_nok_position():
    nok = next(item for item in WATCHLIST if item.ticker == "NOK.US")
    assert score_watchlist_item(nok) < 80
    signal = generate_signal(nok)
    assert signal.side == Side.buy
    assert signal.confidence < 0.5
    assert "观察" in signal.reason


def test_overheated_smr_generates_sell_signal():
    smr = next(item for item in WATCHLIST if item.ticker == "SMR.US")
    signal = generate_signal(smr)
    assert signal.side == Side.sell
    assert "估值过热" in signal.reason


def test_backtest_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(
        strategy_module,
        "daily_close_series",
        lambda ticker, start_date, end_date: [
            ("2026-05-01", 100.0),
            ("2026-05-15", 104.0),
            ("2026-06-01", 101.0),
            ("2026-06-15", 108.0),
            ("2026-07-01", 106.0),
            ("2026-07-16", 112.0),
        ],
    )
    result = run_backtest("pe_v1", "NOK.US")
    assert result.ticker == "NOK.US"
    assert result.trades >= 1
    assert 1 <= len(result.records) <= 7


def test_all_models_and_current_tickers_can_backtest(monkeypatch):
    def fake_daily_close_series(ticker, start_date, end_date):
        return [
            ("2026-05-01", 100.0),
            ("2026-05-15", 104.0),
            ("2026-06-01", 101.0),
            ("2026-06-15", 108.0),
            ("2026-07-01", 106.0),
            ("2026-07-16", 112.0),
        ]

    monkeypatch.setattr(strategy_module, "daily_close_series", fake_daily_close_series)
    for strategy_id in ("pe_v1", "peg_v1", "roi_v1"):
        for item in WATCHLIST:
            result = run_backtest(strategy_id, item.ticker)
            assert result.strategy_id == strategy_id
            assert result.ticker == item.ticker
            assert result.records


def test_risk_blocks_single_position_limit():
    engine = RiskEngine(RiskConfig(account_value=100000))
    request = OrderRequest(ticker="SMR.US", side=Side.buy, qty=20, limit_price=1000)
    decision = engine.evaluate_order(request)
    assert not decision.allowed
    assert "单票" in decision.blocked_reason


def test_risk_blocks_when_automation_paused():
    engine = RiskEngine(RiskConfig(automation_paused=True))
    request = OrderRequest(ticker="NOK.US", side=Side.buy, qty=1, limit_price=11.23)
    decision = engine.evaluate_order(request)
    assert not decision.allowed
    assert "暂停" in decision.blocked_reason


def test_usmart_prepare_order_blocks_without_credentials():
    adapter = USmartBrokerAdapter(live=False)
    request = OrderRequest(ticker="NOK.US", side=Side.buy, qty=1, limit_price=11.23)
    prepared = adapter.prepare_order(request)
    assert prepared.body["exchangeType"] == 5
    assert prepared.body["entrustType"] == 0
    assert "CHANNEL_MISSING" in prepared.blockers


def test_market_quotes_fallback_returns_requested_symbol():
    quotes = market_quotes(["NOK.US"])
    assert quotes[0].ticker == "NOK.US"
    assert quotes[0].price > 0


def test_market_quotes_use_previous_close_when_market_closed(monkeypatch):
    monkeypatch.setattr(data_sources_module, "is_us_market_open", lambda: False)
    monkeypatch.setattr(
        data_sources_module,
        "previous_close_quotes",
        lambda tickers: (
            [
                MarketQuote(
                    ticker=ticker,
                    name=f"{ticker} Test",
                    price=394.46,
                    change=-1.72,
                    pct_change=-0.43,
                    volume=0,
                    source="Yahoo previous close",
                    delay_seconds=0,
                    updated_at="07/15 16:00",
                )
                for ticker in tickers
            ],
            [],
        ),
    )
    quotes = market_quotes(["TSLA"])
    assert quotes[0].ticker == "TSLA"
    assert quotes[0].price == 394.46
    assert quotes[0].source == "Yahoo previous close"


def test_gold_monitor_tracks_minsheng_accumulated_gold_plan(monkeypatch):
    monkeypatch.setattr(
        gold_monitor_module,
        "_minsheng_accumulated_gold_quote",
        lambda: {
            "price": 878.2,
            "change": -5.75,
            "pct_change": -0.65,
            "day_high": 881.74,
            "day_low": 876.38,
            "reference_price": 878.17,
            "symbol": "CCB_999933",
            "reference_name": "建设银行主动积存价 / 银行积存金真实分时参考",
            "status": "交易中",
            "time": "07/16 18:31:00",
            "trend_points": [{"time": f"18:{minute:02d}", "price": 878.2 + minute / 100} for minute in range(20)],
            "source": "test quote",
        },
    )
    snapshot = gold_monitor_snapshot()
    assert snapshot.product_name == "民生积存金"
    assert snapshot.planned_capital == 10000
    assert snapshot.live_price > 0
    assert snapshot.estimated_grams > 11
    assert "¥900" in snapshot.trade_rule
    assert snapshot.refresh_seconds == 10
    assert len(snapshot.trend_points) >= 20
    assert snapshot.reference_symbol in {"CCB_999933", "SGE_AU9999", "CMBC_BANK_GOLD"}
    assert snapshot.watch_points


def test_gold_monitor_uses_last_cache_when_bank_gold_is_closed(monkeypatch, tmp_path):
    cache_path = tmp_path / "gold_quote.json"
    monkeypatch.setattr(gold_monitor_module, "GOLD_QUOTE_CACHE_PATH", cache_path)
    cached_quote = {
        "price": 879.5,
        "change": 1.3,
        "pct_change": 0.15,
        "day_high": 881.0,
        "day_low": 876.0,
        "reference_price": 878.2,
        "symbol": "CCB_999933",
        "reference_name": "建设银行主动积存价 / 银行积存金真实分时参考",
        "status": "交易中",
        "time": "07/17 23:59:00",
        "trend_points": [{"time": "23:59", "price": 879.5}],
        "source": "test cached ccb quote",
        "cached_at": "2026-07-17T23:59:00+08:00",
    }
    cache_path.write_text(gold_monitor_module.json.dumps(cached_quote, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(gold_monitor_module, "_is_bank_gold_trading_session", lambda now=None: False)

    snapshot = gold_monitor_snapshot()

    assert snapshot.live_price == 879.5
    assert not snapshot.is_trading_session
    assert "休市" in snapshot.trading_status
    assert "最后报价" in snapshot.trading_status
    assert "缓存" in snapshot.source
    assert len(snapshot.trend_points) == 12
    assert snapshot.trend_points[-1].time == "23:59"
    assert snapshot.trend_points[-1].price == 879.5


def test_gold_manual_trade_records_real_offline_execution():
    before = len(main_module.gold_manual_trades())
    trade = main_module.create_gold_manual_trade(
        GoldManualTradeRequest(
            amount_cny=1000,
            price=880,
            executed_at="2026-07-16 20:45",
            note="test manual bank app buy",
        )
    )
    assert trade.grams == round(1000 / 880, 4)
    assert trade.price == 880
    assert len(main_module.gold_manual_trades()) == before + 1
    assert main_module.gold_manual_trades()[0].id == trade.id
    snapshot = main_module.gold_monitor()
    assert snapshot.holding_grams >= trade.grams
    assert snapshot.average_cost > 0
    assert snapshot.remaining_capital < snapshot.planned_capital
    assert main_module.delete_gold_manual_trade(trade.id) == {"deleted": trade.id}
    assert len(main_module.gold_manual_trades()) == before


def test_previous_close_import_updates_holdings(monkeypatch):
    def fake_previous_close(tickers):
        return [
            MarketQuote(ticker=ticker, name=ticker, price=12.0, change=0.1, pct_change=0.84, volume=0, source="test previous close", delay_seconds=0, updated_at="07/15 16:00")
            for ticker in tickers
        ], []

    monkeypatch.setattr(main_module, "previous_close_quotes", fake_previous_close)
    result = main_module.import_previous_close()
    assert result.imported >= 1
    assert result.source == "昨收快照"
    assert result.holdings[0].market_price == 12.0
    assert result.account_total > 0


def test_watchlist_add_and_advice_endpoints(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "validate_yahoo_ticker",
        lambda ticker: MarketQuote(ticker=ticker, name=f"{ticker} Test", price=100, change=1, pct_change=1, volume=0, source="test", delay_seconds=0, updated_at="07/15 16:00"),
    )
    added = main_module.add_watchlist_item(AddWatchlistRequest(ticker="QQQ"))
    assert added.ticker == "QQQ"
    assert main_module.validate_ticker("QQQ").valid
    assert main_module.delete_watchlist_item("QQQ") == {"deleted": "QQQ"}
    assert main_module.holding_advice()
    assert main_module.screening_candidates()
    allocation = main_module.portfolio_optimization()
    assert allocation.suggestions
    assert allocation.cash_target > 0


def test_watchlist_add_rejects_invalid_ticker(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "validate_yahoo_ticker",
        lambda ticker: (_ for _ in ()).throw(ValueError("unknown ticker")),
    )
    try:
        main_module.add_watchlist_item(AddWatchlistRequest(ticker="NOTAREALSTOCK123"))
    except Exception as exc:
        assert "未能识别" in str(exc.detail)
    else:
        raise AssertionError("invalid ticker should not be added")


def test_watchlist_delete_blocks_current_holding():
    try:
        main_module.delete_watchlist_item("NOK.US")
    except Exception as exc:
        assert "持仓" in str(exc.detail)
    else:
        raise AssertionError("current holding should not be deletable")


def test_model_validation_returns_all_strategies(monkeypatch):
    monkeypatch.setattr(
        strategy_module,
        "daily_close_series",
        lambda ticker, start_date, end_date: [
            ("2026-05-01", 100.0),
            ("2026-05-15", 104.0),
            ("2026-06-01", 101.0),
            ("2026-06-15", 108.0),
            ("2026-07-01", 106.0),
            ("2026-07-16", 112.0),
        ],
    )
    validation = main_module.model_validation()
    assert {item.strategy_id for item in validation} == {"pe_v1", "peg_v1", "roi_v1"}


def test_import_broker_records_updates_holdings_and_trades():
    result = import_broker_records(
        BrokerImportRequest(
            broker="usmart",
            records=[
                BrokerImportRecord(
                    broker="usmart",
                    record_type="holding",
                    ticker="NOK.US",
                    qty=2,
                    price=11.23,
                    executed_at="07/16 15:30",
                ),
                BrokerImportRecord(
                    broker="usmart",
                    record_type="trade",
                    ticker="NOK.US",
                    side=Side.buy,
                    qty=2,
                    price=11.23,
                    executed_at="07/16 15:31",
                ),
            ],
        )
    )
    assert result.imported == 2
    assert result.holdings_updated == 1
    assert result.trades_recorded == 1


def test_usmart_screenshot_template_parser_extracts_holdings():
    net_asset, holdings, warnings = parse_usmart_portfolio_screenshot()
    assert net_asset == 1784.16
    assert {holding.ticker for holding in holdings} == {"NOK.US", "SMR.US"}
    assert next(holding for holding in holdings if holding.ticker == "NOK.US").qty == 99
    assert "TEMPLATE_V1_USED" in warnings


def test_screenshot_template_can_be_labeled_as_za_bank():
    _, holdings, _ = parse_usmart_portfolio_screenshot(broker="za-bank")
    assert {holding.broker for holding in holdings} == {"za-bank"}


def test_za_bank_screenshot_template_parser_extracts_holdings():
    holdings, warnings = parse_za_bank_portfolio_screenshot()
    assert {holding.ticker for holding in holdings} == {"NOK", "IAU", "NVDA"}
    assert next(holding for holding in holdings if holding.ticker == "NOK").qty == 44
    assert next(holding for holding in holdings if holding.ticker == "NVDA").qty == 0.0005
    assert "ZA_TEMPLATE_V1_USED" in warnings
