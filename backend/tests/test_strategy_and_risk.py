from backend.app.models import OrderRequest, Side
import backend.app.main as main_module
from backend.app.broker import USmartBrokerAdapter
import backend.app.data_sources as data_sources_module
import backend.app.gold_monitor as gold_monitor_module
from fastapi.testclient import TestClient
from backend.app.data_sources import market_quotes
from backend.app.gold_monitor import gold_monitor_snapshot
from backend.app.main import import_broker_records
from backend.app.models import AccountBalance, AccountCashUpdateRequest, AddWatchlistRequest, BrokerImportRecord, BrokerImportRequest, CandidateStock, GoldManualTradeRequest, Holding, ManualExecutionRequest, MarketQuote, ModelValidationItem, TradePlanItem, WatchlistItem
from backend.app.usmart_importer import parse_usmart_portfolio_screenshot
from backend.app.za_importer import parse_za_bank_portfolio_screenshot
from backend.app.risk import RiskConfig, RiskEngine
from backend.app.seed import WATCHLIST
import backend.app.strategy as strategy_module
from backend.app.strategy import generate_signal, run_backtest, score_watchlist_item


def test_brianhub_sso_header_authorizes_protected_api(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "secret")
    client = TestClient(main_module.app)

    missing_auth = client.get("/dashboard/summary")
    assert missing_auth.status_code == 401

    sso_auth = client.get("/dashboard/summary", headers={"X-BrianHub-SSO": "1"})
    assert sso_auth.status_code == 200


def test_factor_score_and_signal_for_current_nok_position():
    item = WatchlistItem(
        ticker="LOW.TEST",
        name="Low Score Test",
        sector="Test",
        pe=38,
        peg=2.4,
        roi=7,
        growth=3,
        trend="下行",
        eligible=False,
        signal="WATCH",
    )
    assert score_watchlist_item(item) < 80
    signal = generate_signal(item)
    assert signal.side == Side.buy
    assert signal.confidence < 0.5
    assert "观察" in signal.reason


def test_overheated_smr_generates_sell_signal():
    item = WatchlistItem(
        ticker="HOT.TEST",
        name="Overheated Test",
        sector="Test",
        pe=88,
        peg=4.8,
        roi=-10,
        growth=20,
        trend="过热",
        eligible=False,
        signal="RISK",
    )
    signal = generate_signal(item)
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


def test_market_quotes_fallback_returns_requested_symbol(monkeypatch):
    monkeypatch.setattr(data_sources_module, "is_us_market_open", lambda: True)
    monkeypatch.setattr(data_sources_module, "_fmp_quotes", lambda tickers: (_ for _ in ()).throw(ValueError("fmp down")))
    monkeypatch.setattr(data_sources_module, "_akshare_quotes", lambda tickers: (_ for _ in ()).throw(ValueError("akshare down")))
    monkeypatch.setattr(
        data_sources_module,
        "_yahoo_quotes",
        lambda tickers: [
            MarketQuote(ticker=ticker, name=ticker, price=12.34, change=0.1, pct_change=0.8, volume=1000, source="test yahoo", delay_seconds=60, updated_at="07/21 10:00")
            for ticker in tickers
        ],
    )
    quotes = market_quotes(["NOK.US"])
    assert quotes[0].ticker == "NOK.US"
    assert quotes[0].price == 12.34


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
    monkeypatch.setattr(main_module, "dynamic_watchlist", lambda items, holdings=None, validation=None, quotes=None: items)
    added = main_module.add_watchlist_item(AddWatchlistRequest(ticker="QQQ"))
    assert added.ticker == "QQQ"
    assert main_module.validate_ticker("QQQ").valid
    assert main_module.delete_watchlist_item("QQQ") == {"deleted": "QQQ"}
    assert main_module.holding_advice()
    cached_candidate = CandidateStock(
        ticker="CACHE",
        name="Cached Candidate",
        sector="Test",
        price=5,
        score=70,
        reason="中长期真实筛选；cached test",
        action="观察候选",
        liquidity_score=80,
        dollar_volume=8_000_000,
        market_cap=250_000_000,
        exchange="NASDAQ",
        data_status="真实缓存",
    )
    monkeypatch.setattr(main_module, "SCREENING_CACHE", (main_module.time.time(), [cached_candidate]))
    assert main_module.screening_candidates()
    allocation = main_module.portfolio_optimization()
    assert allocation.suggestions
    assert allocation.cash_target > 0


def test_execution_plan_keeps_duplicate_ticker_accounts_separate(monkeypatch):
    original_holdings = list(main_module.HOLDINGS)
    original_cash = dict(main_module.ACCOUNT_CASH_BALANCES)
    try:
        main_module.HOLDINGS[:] = [
            Holding(broker="za-bank", ticker="NOK.US", qty=10, avg_cost=8, market_price=10, market_value=100, pnl=20, updated_at="test"),
            Holding(broker="usmart", ticker="NOK.US", qty=99, avg_cost=16.005, market_price=10, market_value=990, pnl=-594.5, updated_at="test"),
        ]
        main_module.ACCOUNT_CASH_BALANCES.update({"za-bank": 200, "usmart": 600.62})
        monkeypatch.setattr(main_module, "WATCHLIST", [
            WatchlistItem(ticker="NOK.US", name="Nokia", sector="Tech", pe=12, peg=1, roi=20, growth=12, trend="横盘", eligible=True, signal="BUY")
        ])
        monkeypatch.setattr(
            main_module,
            "market_quotes",
            lambda tickers: [MarketQuote(ticker="NOK.US", name="Nokia", price=10, change=0, pct_change=0, volume=1000, source="test", delay_seconds=0, updated_at="test")],
        )
        monkeypatch.setattr(main_module, "dynamic_watchlist", lambda items, holdings=None, validation=None, quotes=None: items)

        plans = main_module.execution_plan()

        assert [(plan.broker, plan.ticker) for plan in plans] == [("usmart", "NOK.US"), ("za-bank", "NOK.US")]
        assert {plan.broker: plan.current_amount for plan in plans} == {"za-bank": 100, "usmart": 990}
        assert all(plan.account_name for plan in plans)
    finally:
        main_module.HOLDINGS[:] = original_holdings
        main_module.ACCOUNT_CASH_BALANCES.clear()
        main_module.ACCOUNT_CASH_BALANCES.update(original_cash)


def test_manual_account_cash_update_enables_za_bank_cash(monkeypatch):
    original_cash = dict(main_module.ACCOUNT_CASH_BALANCES)
    monkeypatch.setattr(main_module, "_save_local_state", lambda: None)
    try:
        result = main_module.update_account_cash("za-bank", AccountCashUpdateRequest(available_cash=1250.75, note="manual cash sync"))

        assert result.broker == "za-bank"
        assert result.available_cash == 1250.75
        assert main_module.ACCOUNT_CASH_BALANCES["za-bank"] == 1250.75
    finally:
        main_module.ACCOUNT_CASH_BALANCES.clear()
        main_module.ACCOUNT_CASH_BALANCES.update(original_cash)


def test_core_accounts_are_visible_even_before_cash_is_set():
    original_holdings = list(main_module.HOLDINGS)
    original_cash = dict(main_module.ACCOUNT_CASH_BALANCES)
    try:
        main_module.HOLDINGS[:] = []
        main_module.ACCOUNT_CASH_BALANCES.update({"za-bank": 0, "usmart": 0, "ibkr": 0, "manual": 0})

        balances = main_module._account_balances()

        assert {account.broker for account in balances} == {"za-bank", "usmart"}
    finally:
        main_module.HOLDINGS[:] = original_holdings
        main_module.ACCOUNT_CASH_BALANCES.clear()
        main_module.ACCOUNT_CASH_BALANCES.update(original_cash)


def test_unheld_buy_plan_is_generated_for_each_cash_account(monkeypatch):
    original_holdings = list(main_module.HOLDINGS)
    original_cash = dict(main_module.ACCOUNT_CASH_BALANCES)
    try:
        main_module.HOLDINGS[:] = []
        main_module.ACCOUNT_CASH_BALANCES.update({"za-bank": 1200, "usmart": 600.62, "ibkr": 0, "manual": 0})
        buy_item = WatchlistItem(
            ticker="MSFT",
            name="Microsoft",
            sector="Tech",
            pe=28,
            peg=1.5,
            roi=30,
            growth=12,
            trend="横盘",
            eligible=True,
            signal="BUY",
            model_score=78,
            model_reason="long-term model quality",
        )
        monkeypatch.setattr(main_module, "WATCHLIST", [buy_item])
        monkeypatch.setattr(
            main_module,
            "market_quotes",
            lambda tickers: [MarketQuote(ticker="MSFT", name="Microsoft", price=100, change=0, pct_change=0, volume=1000, source="test", delay_seconds=0, updated_at="test")],
        )
        monkeypatch.setattr(main_module, "dynamic_watchlist", lambda items, holdings=None, validation=None, quotes=None: items)

        plans = main_module.execution_plan()

        brokers = {plan.broker for plan in plans if plan.ticker == "MSFT"}
        assert {"za-bank", "usmart"}.issubset(brokers)
        assert all("中长线" in plan.reason or "分批" in plan.reason for plan in plans)
    finally:
        main_module.HOLDINGS[:] = original_holdings
        main_module.ACCOUNT_CASH_BALANCES.clear()
        main_module.ACCOUNT_CASH_BALANCES.update(original_cash)


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


def test_screening_candidates_returns_cached_payload_without_scan(monkeypatch):
    cached_candidate = CandidateStock(
        ticker="FAST",
        name="Fast Cache",
        sector="Test",
        price=4.5,
        score=72,
        reason="中长期真实筛选；cached payload",
        action="观察候选",
        liquidity_score=82,
        dollar_volume=12_000_000,
        market_cap=320_000_000,
        exchange="NASDAQ",
        data_status="真实缓存",
    )
    monkeypatch.setattr(main_module, "SCREENING_CACHE", None)
    monkeypatch.setattr(main_module, "_cached_candidates", lambda: [cached_candidate])
    monkeypatch.setattr(main_module, "_start_screening_refresh", lambda: None)
    monkeypatch.setattr(
        main_module,
        "_build_screening_candidates",
        lambda: (_ for _ in ()).throw(AssertionError("should not synchronously scan when cache exists")),
    )

    candidates = main_module.screening_candidates()

    assert candidates == [cached_candidate]
    assert candidates[0].data_status == "真实缓存"


def test_old_candidate_cache_is_ignored_for_long_term_screening(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "latest_screening_payload",
        lambda name: [{
            "ticker": "OLD",
            "name": "Old Candidate",
            "sector": "Test",
            "price": 5,
            "score": 72,
            "reason": "全价位真实筛选；old short term payload",
            "action": "加入监控",
        }],
    )

    assert main_module._cached_candidates() == []


def test_candidate_filters_require_liquidity_and_listed_common_stock_without_price_cap():
    accepted = {
        "symbol": "GOOD",
        "price": 45.2,
        "volume": 1_200_000,
        "marketCap": 300_000_000,
        "exchangeShortName": "NASDAQ",
        "type": "stock",
    }
    low_liquidity = {**accepted, "symbol": "THIN", "volume": 100_000}
    wrong_exchange = {**accepted, "symbol": "OTC", "exchangeShortName": "OTC"}
    etf = {**accepted, "symbol": "ETF", "type": "etf"}

    assert main_module._passes_low_price_filters(accepted)
    assert not main_module._passes_low_price_filters(low_liquidity)
    assert not main_module._passes_low_price_filters(wrong_exchange)
    assert not main_module._passes_low_price_filters(etf)


def test_candidate_action_waits_for_pullback_when_valuation_is_overheated(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_candidate_model_summary",
        lambda ticker: {"score": 88, "best_strategy": "peg_v1", "data_quality": 95.0, "missing_samples": 0},
    )
    monkeypatch.setattr(
        main_module,
        "_third_party_reference",
        lambda ticker: {"sentiment": "positive", "summary": "第三方参考偏正面", "source": "test"},
    )
    monkeypatch.setattr(main_module, "_candidate_price", lambda ticker: 120.0)
    item = WatchlistItem(
        ticker="HOTGROW",
        name="Hot Growth",
        sector="Tech",
        pe=82,
        peg=3.4,
        roi=28,
        growth=24,
        trend="过热",
        eligible=False,
        signal="WATCH",
    )

    candidate = main_module._candidate_from_watchlist_item(
        item,
        {"price": 120, "volume": 3_000_000, "marketCap": 8_000_000_000, "dollarVolume": 360_000_000, "exchangeShortName": "NASDAQ"},
    )

    assert candidate.action == "估值偏贵，等回调"
    assert "中长期" in candidate.reason
    assert "估值偏贵" in candidate.reason


def test_candidate_action_requires_long_term_quality_before_joining_watchlist(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_candidate_model_summary",
        lambda ticker: {"score": 82, "best_strategy": "roi_v1", "data_quality": 92.0, "missing_samples": 0},
    )
    monkeypatch.setattr(
        main_module,
        "_third_party_reference",
        lambda ticker: {"sentiment": "positive", "summary": "第三方参考偏正面", "source": "test"},
    )
    monkeypatch.setattr(main_module, "_candidate_price", lambda ticker: 48.0)
    item = WatchlistItem(
        ticker="QUAL",
        name="Quality Compounder",
        sector="Healthcare",
        pe=24,
        peg=1.4,
        roi=26,
        growth=14,
        trend="横盘",
        eligible=True,
        signal="BUY",
    )

    candidate = main_module._candidate_from_watchlist_item(
        item,
        {"price": 48, "volume": 2_200_000, "marketCap": 5_000_000_000, "dollarVolume": 105_600_000, "exchangeShortName": "NYSE"},
    )

    assert candidate.action == "中长期候选"
    assert candidate.score >= 75
    assert "质量" in candidate.reason


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


def test_watchlist_uses_cached_daily_closes_for_technical_fields(monkeypatch):
    item = WatchlistItem(
        ticker="TECH",
        name="Technical Test",
        sector="Test",
        pe=12,
        peg=1,
        roi=20,
        growth=12,
        trend="横盘",
        eligible=False,
        signal="WATCH",
    )
    quote = MarketQuote(ticker="TECH", name="Technical Test", price=12.0, change=0.2, pct_change=1.69, volume=2_000_000, source="test realtime", delay_seconds=0, updated_at="07/21 10:00")
    monkeypatch.setattr(
        data_sources_module,
        "cached_daily_closes",
        lambda ticker, start_date, end_date: [(f"2026-07-{day:02d}", 10 + day / 10) for day in range(1, 21)],
    )

    dynamic = data_sources_module._dynamic_watchlist_item(item, quote, {}, None, {"score": 70, "reason": "test validation"})

    assert dynamic.ma5 > 0
    assert dynamic.ma20 > 0
    assert dynamic.atr20 > 0
    assert "MA5/20" in dynamic.watch_reason


def test_model_validation_uses_short_lived_cache(monkeypatch):
    main_module.MODEL_VALIDATION_CACHE = None
    calls = {"count": 0}

    def fake_compute():
        calls["count"] += 1
        return [
            ModelValidationItem(
                strategy_id="pe_v1",
                tested=1,
                best_ticker="TECH",
                average_annual_return=12,
                average_max_drawdown=-8,
                tuning_note="test",
            )
        ], {"TECH": {"score": 70, "reason": "cached"}}

    monkeypatch.setattr(main_module, "_compute_model_validation", fake_compute)
    monkeypatch.setattr(main_module, "save_screening_payload", lambda name, payload: None)

    first = main_module.model_validation()
    second = main_module.model_validation()

    assert first == second
    assert calls["count"] == 1
    assert main_module.MODEL_VALIDATION_BY_TICKER["TECH"]["score"] == 70


def test_daily_snapshot_and_review_use_local_payloads(monkeypatch):
    watch_item = WatchlistItem(
        ticker="SNAP",
        name="Snapshot Test",
        sector="Test",
        pe=18,
        peg=1.2,
        roi=18,
        growth=10,
        trend="上行",
        eligible=True,
        signal="BUY",
        watch_score=72,
        watch_label="强势上行",
    )
    plan_item = TradePlanItem(
        ticker="SNAP",
        name="Snapshot Test",
        broker="manual",
        signal="BUY",
        model_score=70,
        action="分批买入",
        side="BUY",
        current_weight=0,
        target_weight=5,
        current_amount=0,
        target_amount=100,
        delta_amount=100,
        reference_price=10,
        suggested_qty=10,
        stop_loss_price=9,
        take_profit_price=12,
        confidence=0.7,
        reason="test plan",
        blockers=[],
    )
    saved = {}
    monkeypatch.setattr(main_module, "watchlist", lambda: [watch_item])
    monkeypatch.setattr(main_module, "execution_plan", lambda: [plan_item])
    monkeypatch.setattr(main_module, "_cached_candidates", lambda: [])
    monkeypatch.setattr(main_module, "_account_balances", lambda: [
        AccountBalance(broker="manual", name="Manual", available_cash=100, holding_value=0, account_total=100, updated_at="test", source="test")
    ])
    monkeypatch.setattr(main_module, "notifications", lambda: [])
    monkeypatch.setattr(main_module, "save_screening_payload", lambda name, payload: saved.setdefault(name, payload))

    result = main_module.create_daily_snapshot()
    monkeypatch.setattr(main_module, "latest_screening_payload", lambda name: saved.get(name))
    review = main_module.daily_review()

    assert result["saved"]
    assert result["trade_actions"] == 1
    assert review.snapshot_source == "本地每日快照"
    assert review.next_day_focus


def test_notifications_warn_when_cash_cushion_or_data_is_not_realtime(monkeypatch):
    watch_item = WatchlistItem(
        ticker="CACHE",
        name="Cache Test",
        sector="Test",
        pe=18,
        peg=1.2,
        roi=18,
        growth=10,
        trend="横盘",
        eligible=False,
        signal="WATCH",
        data_status="昨收",
    )
    monkeypatch.setattr(main_module, "_cash_balance", lambda: 1)
    monkeypatch.setattr(main_module, "_cash_target", lambda: 100)
    monkeypatch.setattr(main_module, "watchlist", lambda: [watch_item])

    notices = main_module.notifications()

    assert any(item.id == "cash-cushion" for item in notices)
    assert any(item.id == "data-CACHE" for item in notices)



def test_delete_manual_execution_rolls_back_order_event_cash_and_holding(monkeypatch):
    monkeypatch.setattr(main_module, "_refresh_holding_quote", lambda holding: False)
    monkeypatch.setattr(main_module, "_save_local_state", lambda: None)
    ticker = "UNDO.TEST"
    before_cash = main_module.ACCOUNT_CASH_BALANCES.get("manual", 0.0)
    before_orders = len(main_module.ORDERS)
    before_events = len(main_module.EVENTS)
    request = ManualExecutionRequest(
        broker="other",
        ticker=ticker,
        side=Side.buy,
        qty=3,
        price=4.0,
        executed_at="2026-07-22T12:30",
        note="test rollback",
    )

    order = main_module.create_manual_execution(request)
    assert order.order_type == "MANUAL"
    assert any(holding.ticker == ticker and holding.broker == "manual" for holding in main_module.HOLDINGS)
    assert main_module.ACCOUNT_CASH_BALANCES["manual"] == round(before_cash - 12.0, 2)

    result = main_module.delete_manual_execution(order.id)

    assert result["deleted"] == order.id
    assert len(main_module.ORDERS) == before_orders
    assert len(main_module.EVENTS) == before_events
    assert not any(holding.ticker == ticker and holding.broker == "manual" for holding in main_module.HOLDINGS)
    assert main_module.ACCOUNT_CASH_BALANCES["manual"] == before_cash


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
