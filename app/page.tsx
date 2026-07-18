"use client";

import {
  Activity,
  BarChart3,
  Bot,
  CirclePause,
  Coins,
  Database,
  Gauge,
  Layers3,
  LineChart,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Radar,
  ShieldCheck,
  SlidersHorizontal,
  WalletCards
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const USMART_SCREENSHOT_PATH =
  "/Users/brian/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_5oxgvzo5wkcv21_448a/temp/RWTemp/2026-07/b3cb3351d259bd6f77573a1d380b26e0.jpg";
const ZA_SCREENSHOT_PATH =
  "/Users/brian/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_5oxgvzo5wkcv21_448a/temp/RWTemp/2026-07/4ce6a65a5e65b7986b40f0da36549bc8.jpg";
const APP_PASSWORD_STORAGE_KEY = "us-stock-cockpit-password";

function hasStoredAppPassword() {
  return typeof window !== "undefined" && Boolean(window.localStorage.getItem(APP_PASSWORD_STORAGE_KEY));
}

type DashboardSummary = {
  account_total: number;
  today_pnl: number;
  pnl_label: string;
  discipline_score: number;
  active_signals: number;
  signal_breakdown: { buy: number; sell: number; hold: number; watch: number };
  max_drawdown: number;
  max_drawdown_limit: number;
  execution_mode: string;
  automation_paused: boolean;
  global_risk: string;
  data_source: string;
  sync_status: string;
  local_saved_at: string;
  today_orders: string;
  workflow: { step: number; title: string; detail: string; status: string }[];
  checks: { severity: "ok" | "warn" | "risk"; title: string; detail: string; time: string }[];
};

type StrategyModel = {
  id: string;
  name: string;
  factor_set: string[];
  universe: string[];
  status: string;
  score: number;
  annual_return: number;
  max_drawdown: number;
  trades: number;
  description: string;
};

type WatchlistItem = {
  ticker: string;
  name: string;
  sector: string;
  pe: number;
  peg: number;
  roi: number;
  growth: number;
  trend: string;
  eligible: boolean;
  signal: string;
  signal_reason: string;
  model_score: number;
  model_reason: string;
};

type DisciplineEvent = {
  id: string;
  ticker: string;
  title: string;
  reason: string;
  action: string;
  severity: "ok" | "warn" | "risk";
  created_at: string;
};

type Order = {
  id: string;
  broker: string;
  ticker: string;
  side: string;
  qty: number;
  order_type: string;
  limit_price: number;
  status: string;
  created_at: string;
};

type OfflineTradeForm = {
  broker: "za-bank" | "usmart" | "ibkr" | "other";
  ticker: string;
  side: "BUY" | "SELL";
  qty: string;
  price: string;
  executed_at: string;
  note: string;
};

type RiskStatus = {
  allowed: boolean;
  blocked_reason: string;
  position_limit: number;
  total_exposure_limit: number;
  daily_loss_state: string;
  daily_loss_limit: number;
  weekly_loss_limit: number;
};

type BrokerCapability = {
  id: string;
  name: string;
  status: "tradable" | "manual" | "backup";
  supports_us_stock_orders: boolean;
  integration: string;
  notes: string[];
};

type ExecutionConfig = {
  mode: string;
  live_trading_enabled: boolean;
  usmart_base_url: string;
  usmart_channel: string;
  notes: string[];
};

type PreparedOrder = {
  broker: string;
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: Record<string, string | number | boolean>;
  ready_to_submit: boolean;
  blockers: string[];
};

type MarketQuote = {
  ticker: string;
  name: string;
  price: number;
  change: number;
  pct_change: number;
  volume: number;
  source: string;
  delay_seconds: number;
  updated_at: string;
};

type DataSourceStatus = {
  id: string;
  name: string;
  purpose: string;
  configured: boolean;
  status: "active" | "fallback" | "missing" | "manual";
  detail: string;
};

type Holding = {
  broker: "za-bank" | "usmart" | "ibkr" | "manual";
  ticker: string;
  qty: number;
  avg_cost: number;
  market_price: number;
  market_value: number;
  pnl: number;
  currency: string;
  updated_at: string;
};

type AccountBalance = {
  broker: "za-bank" | "usmart" | "ibkr" | "manual";
  name: string;
  available_cash: number;
  holding_value: number;
  account_total: number;
  currency: string;
  updated_at: string;
  source: string;
};

type USmartScreenshotResult = {
  broker: "usmart";
  image_path: string;
  net_asset: number;
  imported_holdings: number;
  warnings: string[];
  holdings: Holding[];
};

type ZABankScreenshotResult = {
  broker: "za-bank";
  image_path: string;
  imported_holdings: number;
  warnings: string[];
  holdings: Holding[];
};

type GoldMonitor = {
  product_code: string;
  product_name: string;
  product_type: string;
  trading_status: string;
  risk_level: string;
  currency: string;
  planned_capital: number;
  live_price: number;
  change: number;
  pct_change: number;
  day_high: number;
  day_low: number;
  reference_price: number;
  quote_time: string;
  min_purchase_amount: number;
  increment_amount: number;
  buy_fee_rate: number;
  estimated_grams: number;
  first_order_amount: number;
  first_order_grams: number;
  reserve_cash: number;
  remaining_capital: number;
  holding_grams: number;
  holding_cost: number;
  holding_market_value: number;
  holding_pnl: number;
  holding_pnl_pct: number;
  average_cost: number;
  reference_symbol: string;
  reference_name: string;
  reference_change_pct: number;
  reference_time: string;
  is_trading_session: boolean;
  refresh_seconds: number;
  trend_points: { time: string; price: number }[];
  trade_rule: string;
  settlement_rule: string;
  action: string;
  confidence: number;
  advice: string;
  watch_points: string[];
  source: string;
};

type GoldManualTrade = {
  id: string;
  product_code: string;
  product_name: string;
  side: "BUY" | "SELL";
  amount_cny: number;
  grams: number;
  price: number;
  executed_at: string;
  note: string;
};

type PreviousCloseImportResult = {
  as_of: string;
  source: string;
  imported: number;
  account_total: number;
  total_pnl: number;
  quotes: MarketQuote[];
  holdings: Holding[];
  warnings: string[];
};

type TradePlanItem = {
  ticker: string;
  name: string;
  broker: string;
  signal: string;
  model_score: number;
  action: string;
  side: "BUY" | "SELL" | "NONE";
  current_weight: number;
  target_weight: number;
  current_amount: number;
  target_amount: number;
  delta_amount: number;
  reference_price: number;
  suggested_qty: number;
  stop_loss_price: number;
  take_profit_price: number;
  confidence: number;
  reason: string;
  blockers: string[];
};

type CandidateStock = {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  score: number;
  reason: string;
  action: string;
  model_score: number;
  data_quality: number;
  signal: string;
  reference_source: string;
};

type AllocationSuggestion = {
  ticker: string;
  current_weight: number;
  target_weight: number;
  action: string;
  amount: number;
  reason: string;
};

type PortfolioOptimization = {
  account_total: number;
  cash_balance: number;
  cash_target: number;
  cash_action: string;
  suggestions: AllocationSuggestion[];
};

type ModelValidationItem = {
  strategy_id: string;
  tested: number;
  valid_samples: number;
  missing_samples: number;
  data_quality: number;
  data_quality_label: string;
  best_ticker: string;
  average_annual_return: number;
  average_max_drawdown: number;
  short_return: number;
  short_drawdown: number;
  medium_return: number;
  medium_drawdown: number;
  long_return: number;
  long_drawdown: number;
  tuning_note: string;
};

type BacktestResult = {
  strategy_id: string;
  ticker: string;
  annual_return: number;
  pnl: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  trades: number;
  benchmark_return: number;
  records: { date: string; equity: number; benchmark: number }[];
};

type AppData = {
  summary: DashboardSummary | null;
  strategies: StrategyModel[];
  watchlist: WatchlistItem[];
  events: DisciplineEvent[];
  orders: Order[];
  risk: RiskStatus | null;
  brokers: BrokerCapability[];
  execution: ExecutionConfig | null;
  quotes: MarketQuote[];
  sources: DataSourceStatus[];
  holdings: Holding[];
  accountBalances: AccountBalance[];
  tradePlan: TradePlanItem[];
  candidates: CandidateStock[];
  allocation: PortfolioOptimization | null;
  gold: GoldMonitor | null;
  goldTrades: GoldManualTrade[];
};

const nav = [
  { id: "dashboard", label: "驾驶舱", key: "D", icon: Gauge },
  { id: "strategies", label: "策略模型", key: "S", icon: SlidersHorizontal },
  { id: "watchlist", label: "股票池", key: "W", icon: Layers3 },
  { id: "gold", label: "黄金盯盘", key: "G", icon: Coins },
  { id: "discipline", label: "持仓纪律", key: "H", icon: ShieldCheck },
  { id: "analysis", label: "模型分析", key: "A", icon: BarChart3 }
] as const;

const fmtMoney = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);

const roundMoney = (value: number) => Math.round(value * 100) / 100;

const fmtCny = (value: number) =>
  new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);

const pct = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;

const currentLocalInputValue = () => {
  const now = new Date();
  const offsetMs = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 16);
};

const defaultPriceForTicker = (ticker: string) =>
  ({ "NOK.US": 11.23, "SMR.US": 8.36, NOK: 11.25, IAU: 76.28, NVDA: 212.5 }[ticker] || 100);

function getUSMarketSession(now = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).formatToParts(now);
  const value = (type: string) => parts.find((part) => part.type === type)?.value || "";
  const weekday = value("weekday");
  const hour = Number(value("hour"));
  const minute = Number(value("minute"));
  const minutes = hour * 60 + minute;
  const isWeekday = !["Sat", "Sun"].includes(weekday);
  const isOpen = isWeekday && minutes >= 9 * 60 + 30 && minutes < 16 * 60;
  return {
    isOpen,
    label: isOpen ? "NYSE Open" : "NYSE Closed",
    refreshLabel: isOpen ? "1分钟自动刷新" : "开盘后1分钟刷新"
  };
}

function defaultExecutionTime() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs?: number): Promise<T> {
  const appPassword = typeof window === "undefined" ? "" : window.localStorage.getItem(APP_PASSWORD_STORAGE_KEY) || "";
  const controller = timeoutMs ? new AbortController() : null;
  const timeout = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller?.signal || init?.signal,
      headers: {
        "Content-Type": "application/json",
        ...(appPassword ? { "X-App-Password": appPassword } : {}),
        ...(init?.headers || {})
      },
      cache: "no-store"
    });
    if (!response.ok) {
      let message = `${path} ${response.status}`;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch {
        // Keep the HTTP fallback when the backend did not return JSON.
      }
      if (response.status === 401) {
        message = "需要访问密码";
      }
      throw new Error(message);
    }
    return response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`${path} 请求超时`);
    }
    throw error;
  } finally {
    if (timeout) window.clearTimeout(timeout);
  }
}

export default function Home() {
  const [active, setActive] = useState<(typeof nav)[number]["id"]>("dashboard");
  const [data, setData] = useState<AppData>({
    summary: null,
    strategies: [],
    watchlist: [],
    events: [],
    orders: [],
    risk: null,
    brokers: [],
    execution: null,
    quotes: [],
    sources: [],
    holdings: [],
    accountBalances: [],
    tradePlan: [],
    candidates: [],
    allocation: null,
    gold: null,
    goldTrades: []
  });
  const [newTicker, setNewTicker] = useState("");
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [validation, setValidation] = useState<ModelValidationItem[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("pe_v1");
  const [selectedTicker, setSelectedTicker] = useState("NOK.US");
  const [analysisType, setAnalysisType] = useState("offline");
  const [preparedOrder, setPreparedOrder] = useState<PreparedOrder | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [loading, setLoading] = useState(() => hasStoredAppPassword());
  const [validatingModels, setValidatingModels] = useState(false);
  const [notice, setNotice] = useState("");
  const [authRequired, setAuthRequired] = useState(() => !hasStoredAppPassword());
  const [passwordInput, setPasswordInput] = useState("");
  const [marketSession, setMarketSession] = useState(() => getUSMarketSession());
  const loadingRef = useRef(false);
  const goldLoadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const [summary, strategies, events, orders, risk, brokers, execution, sources, holdings, accountBalances, allocation] = await Promise.all([
        fetchJson<DashboardSummary>("/dashboard/summary"),
        fetchJson<StrategyModel[]>("/strategies"),
        fetchJson<DisciplineEvent[]>("/discipline/events"),
        fetchJson<Order[]>("/orders"),
        fetchJson<RiskStatus>("/risk/status"),
        fetchJson<BrokerCapability[]>("/brokers/capabilities"),
        fetchJson<ExecutionConfig>("/execution/config"),
        fetchJson<DataSourceStatus[]>("/data-sources/status"),
        fetchJson<Holding[]>("/portfolio/holdings"),
        fetchJson<AccountBalance[]>("/portfolio/account-balances"),
        fetchJson<PortfolioOptimization>("/portfolio/optimization")
      ]);
      setData((current) => ({ ...current, summary, strategies, events, orders, risk, brokers, execution, sources, holdings, accountBalances, allocation }));
      setLoading(false);
      fetchJson<WatchlistItem[]>("/watchlist")
        .then((watchlist) => setData((current) => ({ ...current, watchlist })))
        .catch(() => setNotice("股票池实时计算较慢，已先显示账户和持仓数据。"));
      fetchJson<TradePlanItem[]>("/execution/plan")
        .then((tradePlan) => setData((current) => ({ ...current, tradePlan })))
        .catch(() => setNotice("执行计划计算较慢，已先显示账户和持仓数据。"));
      fetchJson<MarketQuote[]>("/market/quotes")
        .then((quotes) => setData((current) => ({ ...current, quotes })))
        .catch(() => setNotice("行情刷新较慢，已先显示账户和策略数据。"));
      fetchJson<CandidateStock[]>("/screening/candidates")
        .then((candidates) => setData((current) => ({ ...current, candidates })))
        .catch(() => setNotice("候选股真实筛选较慢，已先显示持仓和股票池数据。"));
      if (!goldLoadingRef.current) {
        goldLoadingRef.current = true;
        Promise.all([
          fetchJson<GoldMonitor>("/gold/monitor", undefined, 8000),
          fetchJson<GoldManualTrade[]>("/gold/manual-trades", undefined, 8000)
        ])
          .then(([gold, goldTrades]) => setData((current) => ({ ...current, gold, goldTrades })))
          .catch(() => setNotice("黄金盯盘接口较慢，已先显示美股账户和股票池数据。"))
          .finally(() => {
            goldLoadingRef.current = false;
          });
      }
    } finally {
      loadingRef.current = false;
    }
  }, []);

  const loadGold = useCallback(async () => {
    if (goldLoadingRef.current) return;
    goldLoadingRef.current = true;
    try {
      const [gold, goldTrades] = await Promise.all([
        fetchJson<GoldMonitor>("/gold/monitor", undefined, 8000),
        fetchJson<GoldManualTrade[]>("/gold/manual-trades", undefined, 8000)
      ]);
      setData((current) => ({ ...current, gold, goldTrades }));
    } finally {
      goldLoadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (authRequired) {
      setLoading(false);
      return;
    }
    load().catch((error) => {
      setLoading(false);
      if (error instanceof Error && error.message === "需要访问密码") {
        window.localStorage.removeItem(APP_PASSWORD_STORAGE_KEY);
        setAuthRequired(true);
        setNotice("请输入访问密码。");
        return;
      }
      setNotice("后端暂未连接，正在显示前端骨架。");
    });
  }, [authRequired, load]);

  useEffect(() => {
    const timer = window.setInterval(() => setMarketSession(getUSMarketSession()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (authRequired) return undefined;
    const refreshSeconds = marketSession.isOpen ? 60 : data.gold?.is_trading_session ? data.gold.refresh_seconds : 0;
    if (!refreshSeconds) return undefined;
    load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    const timer = window.setInterval(() => {
      load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    }, refreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [authRequired, data.gold?.is_trading_session, data.gold?.refresh_seconds, load, marketSession.isOpen]);

  useEffect(() => {
    if (authRequired) return undefined;
    if (marketSession.isOpen || data.gold?.is_trading_session) return undefined;
    const timer = window.setInterval(() => {
      loadGold().catch(() => setNotice("黄金盯盘刷新失败，正在保留最近一次数据。"));
    }, (data.gold?.refresh_seconds || 60) * 1000);
    return () => window.clearInterval(timer);
  }, [authRequired, data.gold?.is_trading_session, data.gold?.refresh_seconds, loadGold, marketSession.isOpen]);

  useEffect(() => {
    if (authRequired) return;
    runBacktest().catch(() => undefined);
  }, [authRequired]);

  const bestStrategy = useMemo(
    () => data.strategies.find((strategy) => strategy.id === selectedStrategy) || data.strategies[0],
    [data.strategies, selectedStrategy]
  );

  async function runBacktest() {
    try {
      const result = await fetchJson<BacktestResult>(`/strategies/${selectedStrategy}/backtest`, {
        method: "POST",
        body: JSON.stringify({
          ticker: selectedTicker,
          start_date: "2026-05-01",
          end_date: "2026-07-16",
          mode: analysisType
        })
      });
      setBacktest(result);
      setNotice("");
    } catch (error) {
      setBacktest(null);
      setNotice(error instanceof Error ? error.message : "缺少真实历史数据，无法回测。");
    }
  }

  async function toggleAutomation(paused: boolean) {
    await fetchJson(paused ? "/automation/resume" : "/automation/pause", { method: "POST" });
    await load();
  }

  async function previewUsmartOrder() {
    const result = await fetchJson<PreparedOrder>("/orders/preview?target=usmart-paper", {
      method: "POST",
      body: JSON.stringify({
        ticker: selectedTicker,
        side: "BUY",
        qty: 1,
        order_type: "LMT",
        limit_price: defaultPriceForTicker(selectedTicker),
        strategy_id: selectedStrategy,
        dry_run: false
      })
    });
    setPreparedOrder(result);
    setActive("dashboard");
  }

  async function recordZaManualExecution() {
    await submitOfflineTrade({
      broker: "za-bank",
      ticker: selectedTicker,
      side: "BUY",
      qty: "1",
      price: String(defaultPriceForTicker(selectedTicker)),
      executed_at: defaultExecutionTime(),
      note: "ZA Bank App 手工确认"
    });
  }

  async function submitOfflineTrade(form: OfflineTradeForm) {
    const ticker = form.ticker.trim().toUpperCase();
    const qty = Number(form.qty);
    const price = Number(form.price);
    if (!ticker || !Number.isFinite(qty) || qty <= 0 || !Number.isFinite(price) || price <= 0) {
      setNotice("请填写有效的股票代码、数量和成交价。");
      return;
    }
    await fetchJson<Order>("/manual-executions", {
      method: "POST",
      body: JSON.stringify({
        broker: form.broker,
        ticker,
        side: form.side,
        qty,
        price,
        executed_at: form.executed_at || defaultExecutionTime(),
        note: form.note
      })
    });
    await load();
    setNotice(`已记录 ${ticker} ${form.side === "BUY" ? "买入" : "卖出"} ${qty} 股线下交易，并更新本地持仓。`);
  }

  async function importUsmartScreenshot() {
    const result = await fetchJson<USmartScreenshotResult>("/imports/usmart-screenshot", {
      method: "POST",
      body: JSON.stringify({
        image_path: USMART_SCREENSHOT_PATH,
        as_of: "07/16 14:02"
      })
    });
    await load();
    setActive("discipline");
    setNotice(`已从 uSMART 截图导入 ${result.imported_holdings} 条持仓，净资产 ${fmtMoney(result.net_asset)}。`);
  }

  async function importZaScreenshot() {
    const result = await fetchJson<ZABankScreenshotResult>("/imports/za-screenshot", {
      method: "POST",
      body: JSON.stringify({
        image_path: ZA_SCREENSHOT_PATH,
        as_of: "07/16 14:04"
      })
    });
    await load();
    setActive("discipline");
    setNotice(`已从 ZA Bank 截图导入 ${result.imported_holdings} 条持仓。`);
  }

  async function importPreviousClose() {
    const result = await fetchJson<PreviousCloseImportResult>("/market/import-previous-close", { method: "POST" });
    await load();
    setNotice(`已导入 ${result.imported} 条上一交易日收盘价，账户估值 ${fmtMoney(result.account_total)}，持仓盈亏 ${fmtMoney(result.total_pnl)}。`);
    return result;
  }

  async function importPreviousCloseAndBacktest() {
    await importPreviousClose();
    await runBacktest();
    setActive("analysis");
  }

  async function addStockToWatchlist(ticker: string) {
    const normalized = ticker.trim().toUpperCase();
    if (!normalized) return;
    try {
      const added = await fetchJson<WatchlistItem>("/watchlist", {
        method: "POST",
        body: JSON.stringify({ ticker: normalized })
      });
      setNewTicker("");
      await load();
      setNotice(`${added.ticker} 已加入股票池，并已用最新可用行情更新趋势与信号。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加入失败，请稍后重试。");
    }
  }

  async function deleteWatchlistTicker(ticker: string) {
    await fetchJson(`/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
    await load();
    setNotice(`${ticker} 已从股票池删除。`);
  }

  async function validateModels() {
    if (validatingModels) return;
    setValidatingModels(true);
    setNotice("正在批量回测当前股票池，并把模型分写入信号判断...");
    try {
      const result = await fetchJson<ModelValidationItem[]>("/models/validation");
      setValidation(result);
      await load();
      const tested = result.reduce((total, item) => total + item.tested, 0);
      setNotice(`已验证 ${result.length} 个策略模型、${tested} 个股票样本，模型分已更新到股票池和持仓建议。`);
    } catch (error) {
      setNotice(error instanceof Error ? `模型验证失败：${error.message}` : "模型验证失败，请稍后重试。");
    } finally {
      setValidatingModels(false);
    }
  }

  async function unlockApp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = passwordInput.trim();
    if (!trimmed) {
      setNotice("请输入访问密码。");
      return;
    }
    window.localStorage.setItem(APP_PASSWORD_STORAGE_KEY, trimmed);
    setAuthRequired(false);
    setLoading(true);
    try {
      await load();
      setNotice("");
    } catch (error) {
      window.localStorage.removeItem(APP_PASSWORD_STORAGE_KEY);
      setAuthRequired(true);
      setLoading(false);
      setNotice(error instanceof Error ? error.message : "访问密码不正确。");
    }
  }

  function lockApp() {
    window.localStorage.removeItem(APP_PASSWORD_STORAGE_KEY);
    setPasswordInput("");
    setAuthRequired(true);
    setLoading(false);
    setNotice("已锁定，请重新输入访问密码。");
  }

  if (authRequired) {
    return (
      <main className="login-shell">
        <form className="login-panel" onSubmit={unlockApp}>
          <div>
            <span className="login-kicker">US STOCK COCKPIT</span>
            <h1>美股驾驶舱</h1>
            <p>输入访问密码后查看持仓、股票池和交易纪律。</p>
          </div>
          <label>
            <span>访问密码</span>
            <input
              autoFocus
              type="password"
              value={passwordInput}
              onChange={(event) => setPasswordInput(event.target.value)}
              placeholder="请输入 APP_PASSWORD"
            />
          </label>
          <button className="primary" type="submit">进入驾驶舱</button>
          {notice && <small className="login-error">{notice}</small>}
        </form>
      </main>
    );
  }

  return (
    <main className={`shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <div>
            <span>美股驾驶舱</span>
            <small>US STOCK COCKPIT</small>
          </div>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setSidebarCollapsed((value) => !value)}
            aria-label={sidebarCollapsed ? "展开左侧导航" : "折叠左侧导航"}
            title={sidebarCollapsed ? "展开左侧导航" : "折叠左侧导航"}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>
        <nav className="nav">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={active === item.id ? "active" : ""} onClick={() => setActive(item.id)}>
                <kbd>{item.key}</kbd>
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="system-card">
          <p><i /> 系统运行中</p>
          <dl>
            <div><dt>执行模式</dt><dd>{data.summary?.execution_mode || "本地记录"}</dd></div>
            <div><dt>今日订单</dt><dd>{data.summary?.today_orders || "0 / 5"}</dd></div>
            <div><dt>全局风控</dt><dd>{data.summary?.global_risk || "正常"}</dd></div>
            <div><dt>数据源</dt><dd>{data.summary?.data_source || "本地记录"}</dd></div>
            <div><dt>同步状态</dt><dd>{data.summary?.sync_status || "未登录"}</dd></div>
            <div><dt>本地保存</dt><dd>{data.summary?.local_saved_at || "07/16 14:04"}</dd></div>
          </dl>
          <button className="ghost">重置本地数据</button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <h1>{nav.find((item) => item.id === active)?.label}</h1>
          <div className="actions">
            <span className="pill local">本地纪律模式</span>
            <span className="pill">{marketSession.label}</span>
            <span className="pill">{marketSession.refreshLabel}</span>
            <button className="sync" type="button" onClick={lockApp}>
              <LogOut size={15} />
              锁定
            </button>
            <button className="sync" onClick={() => data.summary && toggleAutomation(data.summary.automation_paused)}>
              {data.summary?.automation_paused ? <Play size={15} /> : <CirclePause size={15} />}
              {data.summary?.automation_paused ? "恢复自动执行" : "暂停自动执行"}
            </button>
          </div>
        </header>

        {notice && <div className="notice">{notice}</div>}
        {loading ? <div className="loading">正在加载驾驶舱...</div> : null}

        {active === "dashboard" && data.summary && (
          <Dashboard
            summary={data.summary}
            risk={data.risk}
            orders={data.orders}
            brokers={data.brokers}
            execution={data.execution}
            sources={data.sources}
            preparedOrder={preparedOrder}
            previewUsmartOrder={previewUsmartOrder}
          />
        )}
        {active === "strategies" && <Strategies strategies={data.strategies} />}
        {active === "watchlist" && (
          <Watchlist
            items={data.watchlist}
            quotes={data.quotes}
            holdings={data.holdings}
            accountBalances={data.accountBalances}
            tradePlan={data.tradePlan}
            candidates={data.candidates}
            allocation={data.allocation}
            validation={validation}
            newTicker={newTicker}
            setNewTicker={setNewTicker}
            addStockToWatchlist={addStockToWatchlist}
            deleteWatchlistTicker={deleteWatchlistTicker}
            load={load}
            importPreviousClose={importPreviousClose}
            validateModels={validateModels}
            validatingModels={validatingModels}
          />
        )}
        {active === "gold" && data.gold && <GoldWatch monitor={data.gold} trades={data.goldTrades} loadGold={loadGold} setNotice={setNotice} />}
        {active === "discipline" && (
          <Discipline
            events={data.events}
            orders={data.orders}
            holdings={data.holdings}
            selectedTicker={selectedTicker}
            recordZaManualExecution={recordZaManualExecution}
            submitOfflineTrade={submitOfflineTrade}
            importUsmartScreenshot={importUsmartScreenshot}
            importZaScreenshot={importZaScreenshot}
          />
        )}
        {active === "analysis" && (
          <Analysis
            strategies={data.strategies}
            watchlist={data.watchlist}
            backtest={backtest}
            bestStrategy={bestStrategy}
            selectedStrategy={selectedStrategy}
            selectedTicker={selectedTicker}
            analysisType={analysisType}
            setSelectedStrategy={setSelectedStrategy}
            setSelectedTicker={setSelectedTicker}
            setAnalysisType={setAnalysisType}
            runBacktest={runBacktest}
            importPreviousCloseAndBacktest={importPreviousCloseAndBacktest}
          />
        )}
      </section>
    </main>
  );
}

function Metric({ label, value, hint, tone = "normal", icon: Icon }: { label: string; value: string; hint: string; tone?: string; icon?: typeof Activity }) {
  return (
    <article className={`metric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
      {Icon && <Icon className="metric-icon" size={22} />}
    </article>
  );
}

function Dashboard({
  summary,
  risk,
  orders,
  brokers,
  execution,
  sources,
  preparedOrder,
  previewUsmartOrder
}: {
  summary: DashboardSummary;
  risk: RiskStatus | null;
  orders: Order[];
  brokers: BrokerCapability[];
  execution: ExecutionConfig | null;
  sources: DataSourceStatus[];
  preparedOrder: PreparedOrder | null;
  previewUsmartOrder: () => Promise<void>;
}) {
  return (
    <div className="page-grid">
      <Metric label="账户总额" value={fmtMoney(summary.account_total)} hint={`${fmtMoney(summary.today_pnl)} ${summary.pnl_label || "今日"}`} tone="green" icon={WalletCards} />
      <Metric label="自动化纪律分" value={`${summary.discipline_score}`} hint="本周 2 次人工干预" tone="green" icon={Bot} />
      <Metric label="活跃信号" value={`${summary.active_signals}`} hint={`买入 ${summary.signal_breakdown.buy} / 卖出 ${summary.signal_breakdown.sell} / 持有 ${summary.signal_breakdown.hold} / 观察 ${summary.signal_breakdown.watch}`} tone="amber" icon={Radar} />
      <Metric label="最大回撤" value={pct(summary.max_drawdown)} hint={`策略上限 ${summary.max_drawdown_limit}%`} tone="danger" icon={LineChart} />

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>核心流程</h2>
            <p>每天只看这条主线：模型、股票、行情、信号、执行记录。</p>
          </div>
          <button>查看记录</button>
        </div>
        <div className="flow">
          {summary.workflow.map((step) => (
            <article key={step.step}>
              <b>{step.step}</b>
              <strong>{step.title}</strong>
              <span>{step.detail}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>今日纪律检查</h2>
            <p>每天打开驾驶舱先看这里：需要处理的信号、线下计划、持仓风险和数据状态会自动收敛成行动清单。</p>
          </div>
          <span className="badge">{summary.checks.filter((check) => check.severity !== "ok").length} 项需处理</span>
        </div>
        <div className="event-list">
          {summary.checks.map((check) => (
            <article className={`event ${check.severity}`} key={check.title}>
              <span />
              <div>
                <strong>{check.title}</strong>
                <p>{check.detail}</p>
                <small>{check.time}</small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>风控状态</h2>
        <div className="risk-box">
          <ShieldCheck />
          <strong>{risk?.allowed ? "允许执行" : "已阻断"}</strong>
          <p>{risk?.blocked_reason || "所有订单仍需经过仓位、亏损和频率限制。"}</p>
          <dl>
            <div><dt>单票上限</dt><dd>{risk ? pct(risk.position_limit * 100) : "5%"}</dd></div>
            <div><dt>总仓上限</dt><dd>{risk ? pct(risk.total_exposure_limit * 100) : "50%"}</dd></div>
            <div><dt>日亏停机</dt><dd>{risk ? pct(risk.daily_loss_limit * 100) : "2%"}</dd></div>
          </dl>
        </div>
      </section>

      <section className="panel">
        <h2>最近订单</h2>
        <div className="compact-table">
          {orders.slice(0, 4).map((order) => (
            <div key={order.id}>
              <span>{order.ticker}</span>
              <b>{order.side}</b>
              <em>{order.status}</em>
            </div>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>数据源状态</h2>
            <p>主路径切换为 AKShare 行情、TuShare 基本面、ZA/uSMART 导入对账；券商 API 下单降为未来可选。</p>
          </div>
          <span className="badge">导入对账优先</span>
        </div>
        <div className="source-grid">
          {sources.map((source) => (
            <article key={source.id} className={`source-card ${source.status}`}>
              <strong>{source.name}</strong>
              <span>{source.status}</span>
              <p>{source.purpose}</p>
              <small>{source.detail}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>券商接入路径</h2>
            <p>按你现有账户优先：香港盈立负责自动化交易，ZA Bank 先做手工确认，IBKR 作为备用执行通道。</p>
          </div>
          <button onClick={previewUsmartOrder}>预演 uSMART 订单</button>
        </div>
        <div className="broker-grid">
          {brokers.map((broker) => (
            <article key={broker.id} className={`broker-card ${broker.status}`}>
              <div>
                <strong>{broker.name}</strong>
                <span>{broker.supports_us_stock_orders ? "支持自动下单" : "不接自动下单"}</span>
              </div>
              <p>{broker.integration}</p>
              <ul>
                {broker.notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            </article>
          ))}
        </div>
        <div className="execution-panel">
          <div>
            <strong>当前执行模式</strong>
            <span>{execution?.mode || "paper"} · {execution?.live_trading_enabled ? "live enabled" : "live locked"}</span>
            <p>{execution?.notes?.[1] || "uSMART 需要渠道、token 和 RSA 签名后才能提交。"}</p>
          </div>
          {preparedOrder && (
            <div className="prepared-order">
              <strong>{preparedOrder.broker} 请求预演</strong>
              <span>{preparedOrder.ready_to_submit ? "可提交" : `阻断：${preparedOrder.blockers.join(", ")}`}</span>
              <code>{preparedOrder.method || "POST"} {preparedOrder.url || "/orders"}</code>
              <pre>{JSON.stringify(preparedOrder.body, null, 2)}</pre>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function Strategies({ strategies }: { strategies: StrategyModel[] }) {
  return (
    <div className="page-grid">
      {strategies.map((strategy) => (
        <article className="strategy-card" key={strategy.id}>
          <div>
            <span>{strategy.status}</span>
            <h2>{strategy.name}</h2>
            <p>{strategy.description}</p>
          </div>
          <dl>
            <div><dt>综合评分</dt><dd>{strategy.score}</dd></div>
            <div><dt>年化收益</dt><dd>{pct(strategy.annual_return)}</dd></div>
            <div><dt>最大回撤</dt><dd>{pct(strategy.max_drawdown)}</dd></div>
            <div><dt>交易次数</dt><dd>{strategy.trades}</dd></div>
          </dl>
          <footer>
            {strategy.factor_set.map((factor) => <small key={factor}>{factor}</small>)}
          </footer>
        </article>
      ))}
    </div>
  );
}

function Watchlist({
  items,
  quotes,
  holdings,
  accountBalances,
  tradePlan,
  candidates,
  allocation,
  validation,
  newTicker,
  setNewTicker,
  addStockToWatchlist,
  deleteWatchlistTicker,
  load,
  importPreviousClose,
  validateModels,
  validatingModels
}: {
  items: WatchlistItem[];
  quotes: MarketQuote[];
  holdings: Holding[];
  accountBalances: AccountBalance[];
  tradePlan: TradePlanItem[];
  candidates: CandidateStock[];
  allocation: PortfolioOptimization | null;
  validation: ModelValidationItem[];
  newTicker: string;
  setNewTicker: (value: string) => void;
  addStockToWatchlist: (ticker: string) => Promise<void>;
  deleteWatchlistTicker: (ticker: string) => Promise<void>;
  load: () => Promise<void>;
  importPreviousClose: () => Promise<PreviousCloseImportResult>;
  validateModels: () => Promise<void>;
  validatingModels: boolean;
}) {
  const quoteMap = new Map(quotes.map((quote) => [quote.ticker, quote]));
  const accountTotal = holdings.reduce((sum, holding) => sum + holding.market_value, 0);
  const cashBalance = accountBalances.reduce((sum, account) => sum + account.available_cash, 0);
  const accountEquity = accountBalances.reduce((sum, account) => sum + account.account_total, 0);
  const reserveCash = Math.max(accountEquity * 0.08, 0);
  const deployableCash = Math.max(cashBalance - reserveCash, 0);
  const buyPlans = tradePlan.filter((item) => item.side === "BUY" && item.suggested_qty > 0 && item.blockers.length === 0);
  const reducePlans = tradePlan.filter((item) => item.side === "SELL" && item.suggested_qty > 0);
  const planWeightTotal = buyPlans.reduce((sum, item) => sum + Math.max(item.model_score, 40) * item.confidence, 0) || 1;
  const mixedBuyPlans = buyPlans.map((item) => {
    const weight = Math.max(item.model_score, 40) * item.confidence / planWeightTotal;
    const budget = Math.min(Math.max(deployableCash * weight, 0), Math.abs(item.delta_amount));
    const qty = Math.floor(budget / Math.max(item.reference_price, 0.01));
    return { ...item, budget: roundMoney(qty * item.reference_price), qty };
  }).filter((item) => item.qty > 0);
  const reduceCash = reducePlans.reduce((sum, item) => sum + Math.abs(item.delta_amount), 0);
  const todayDeckAction = deployableCash >= 25 && mixedBuyPlans.length
    ? "可混合加仓"
    : reducePlans.length
      ? "先减仓回收弹药"
      : "观察等待";
  const holdingMap = new Map<string, { qty: number; cost: number; value: number; pnl: number; brokers: Set<string> }>();
  holdings.forEach((holding) => {
    const current = holdingMap.get(holding.ticker) || { qty: 0, cost: 0, value: 0, pnl: 0, brokers: new Set<string>() };
    current.qty += holding.qty;
    current.cost += holding.avg_cost * holding.qty;
    current.value += holding.market_value;
    current.pnl += holding.pnl;
    current.brokers.add(holding.broker);
    holdingMap.set(holding.ticker, current);
  });
  return (
    <div className="page-grid">
      <section className="panel full">
        <div className="panel-head">
          <div>
            <h2>真实持仓与选股池</h2>
            <p>这里同时管理当前持仓、候选股票、实时纪律建议和模型验证，不会自动下单。</p>
          </div>
          <div className="button-row">
            <button onClick={load}>刷新行情</button>
            <button onClick={importPreviousClose}>导入昨收</button>
            <button onClick={validateModels} disabled={validatingModels}>
              {validatingModels ? "验证中..." : "验证模型"}
            </button>
          </div>
        </div>
        <div className="account-balance-grid">
          {accountBalances.map((account) => (
            <article key={account.broker} className="account-balance-card">
              <span>{account.name}</span>
              <strong>{fmtMoney(account.available_cash)}</strong>
              <small>可用余额</small>
              <dl>
                <div><dt>持仓市值</dt><dd>{fmtMoney(account.holding_value)}</dd></div>
                <div><dt>账户合计</dt><dd>{fmtMoney(account.account_total)}</dd></div>
              </dl>
            </article>
          ))}
        </div>
        <div className="add-stock-row">
          <label>新增监控股票
            <input
              value={newTicker}
              onChange={(event) => setNewTicker(event.target.value.toUpperCase())}
              placeholder="例如 MSFT / GOOGL / QQQ"
            />
          </label>
          <button className="primary" disabled={!newTicker.trim()} onClick={() => addStockToWatchlist(newTicker)}>加入股票池</button>
        </div>
        <table className="watchlist-table">
          <thead>
            <tr><th>股票</th><th>现价</th><th>涨跌</th><th>持仓</th><th>成本</th><th>持仓盈亏</th><th>仓位</th><th>PE</th><th>PEG</th><th>ROI</th><th>趋势</th><th>模型分</th><th>信号</th><th>信号依据</th><th>操作</th></tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const quote = quoteMap.get(item.ticker);
              const holding = holdingMap.get(item.ticker);
              const avgCost = holding && holding.qty ? holding.cost / holding.qty : 0;
              const pnlPct = holding && holding.cost ? (holding.pnl / holding.cost) * 100 : 0;
              const weight = holding && accountTotal ? (holding.value / accountTotal) * 100 : 0;
              const hasModelValidation = item.model_reason && item.model_reason !== "尚未验证模型";
              return (
                <tr key={item.ticker}>
                  <td><b>{item.ticker}</b><span>{holding ? `${Array.from(holding.brokers).join(" / ")} · ${item.name}` : item.name}</span></td>
                  <td>{quote ? fmtMoney(quote.price) : "-"}</td>
                  <td className={quote && quote.pct_change < 0 ? "negative" : "positive"}>{quote ? pct(quote.pct_change) : "-"}</td>
                  <td>{holding ? holding.qty.toFixed(holding.qty < 1 ? 4 : 2) : "-"}</td>
                  <td>{holding ? fmtMoney(avgCost) : "-"}</td>
                  <td className={holding && holding.pnl < 0 ? "negative" : "positive"}>{holding ? `${fmtMoney(holding.pnl)} / ${pct(pnlPct)}` : "-"}</td>
                  <td>{holding ? pct(weight) : "-"}</td>
                  <td>{item.pe}</td>
                  <td>{item.peg}</td>
                  <td>{pct(item.roi)}</td>
                  <td>{item.trend}</td>
                  <td className="model-cell">
                    {hasModelValidation ? item.model_score : "-"}
                    <span>{item.model_reason || "点击验证模型后生成"}</span>
                  </td>
                  <td><em>{holding ? `${item.signal} · 持仓纪律` : item.signal}</em></td>
                  <td><span>{item.signal_reason || "-"}</span></td>
                  <td>
                    {holding ? (
                      <span>持仓中</span>
                    ) : (
                      <button onClick={() => deleteWatchlistTicker(item.ticker)}>删除</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>执行策略</h2>
            <p>把股票池信号、模型分、持仓和现金约束转成目标仓位、金额、股数和价格纪律。</p>
          </div>
          <span className="badge">{tradePlan.filter((item) => item.side !== "NONE").length} 个动作</span>
        </div>
        <div className="execution-plan-grid">
          {tradePlan.map((item) => (
            <article key={item.ticker} className={`execution-plan-card ${item.side.toLowerCase()}`}>
              <header>
                <strong>{item.ticker}</strong>
                <b>{item.action}</b>
                <span>{item.signal} · 模型分 {item.model_score || "-"}</span>
              </header>
              <dl>
                <div><dt>方向</dt><dd>{item.side === "NONE" ? "不下单" : item.side}</dd></div>
                <div><dt>建议股数</dt><dd>{item.suggested_qty}</dd></div>
                <div><dt>金额差</dt><dd>{fmtMoney(item.delta_amount)}</dd></div>
                <div><dt>参考价</dt><dd>{fmtMoney(item.reference_price)}</dd></div>
                <div><dt>仓位</dt><dd>{item.current_weight.toFixed(2)}% → {item.target_weight.toFixed(2)}%</dd></div>
                <div><dt>止损/止盈</dt><dd>{fmtMoney(item.stop_loss_price)} / {fmtMoney(item.take_profit_price)}</dd></div>
              </dl>
              <p>{item.reason}</p>
              {item.blockers.length > 0 && <span className="blocker">{item.blockers.join("；")}</span>}
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>今日配舱</h2>
            <p>按账户现金弹药、现金垫、股票池信号和执行策略生成今日混合加仓与减仓顺序。</p>
          </div>
          <span className="badge">{todayDeckAction}</span>
        </div>
        <div className="deck-summary">
          <div><span>总弹药</span><strong>{fmtMoney(cashBalance)}</strong></div>
          <div><span>现金垫</span><strong>{fmtMoney(reserveCash)}</strong></div>
          <div><span>可动用</span><strong>{fmtMoney(deployableCash)}</strong></div>
          <div><span>减仓可回收</span><strong>{fmtMoney(reduceCash)}</strong></div>
        </div>
        <div className="deck-plan-grid">
          <article className="deck-plan-card buy">
            <header>
              <strong>混合加仓</strong>
              <span>{mixedBuyPlans.length ? `${mixedBuyPlans.length} 个标的` : "暂无可执行买入"}</span>
            </header>
            {mixedBuyPlans.length ? (
              <div className="compact-table">
                {mixedBuyPlans.map((item) => (
                  <div key={`deck-buy-${item.ticker}`}>
                    <span>{item.ticker} · 买入参考 {fmtMoney(item.reference_price)} · 止损 {fmtMoney(item.stop_loss_price)} · 止盈 {fmtMoney(item.take_profit_price)}</span>
                    <b>{item.qty} 股</b>
                    <em>{fmtMoney(item.budget)}</em>
                  </div>
                ))}
              </div>
            ) : (
              <p>当前没有同时满足现金垫、BUY 信号、无阻断条件的标的。先保留弹药，等待股票池信号转强。</p>
            )}
          </article>
          <article className="deck-plan-card sell">
            <header>
              <strong>减仓顺序</strong>
              <span>{reducePlans.length ? `${reducePlans.length} 个标的` : "暂无强制减仓"}</span>
            </header>
            {reducePlans.length ? (
              <div className="compact-table">
                {reducePlans.map((item) => (
                  <div key={`deck-sell-${item.ticker}`}>
                    <span>{item.ticker} · 卖出参考 {fmtMoney(item.reference_price)} · 止损 {fmtMoney(item.stop_loss_price)} · 止盈 {fmtMoney(item.take_profit_price)}</span>
                    <b>{item.suggested_qty} 股</b>
                    <em>{fmtMoney(Math.abs(item.delta_amount))}</em>
                  </div>
                ))}
              </div>
            ) : (
              <p>当前执行计划没有生成减仓动作。若需要补足弹药，优先人工检查高亏损、高集中度或模型分偏低的持仓。</p>
            )}
          </article>
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>候选股发现</h2>
            <p>用于寻找适合加入监控的标的，加入后进入同一套行情、信号和回测流程。</p>
          </div>
          <span className="badge">{candidates.length} 个候选</span>
        </div>
        <div className="advice-grid">
          {candidates.map((candidate) => (
            <article key={candidate.ticker} className="advice-card">
              <strong>{candidate.ticker} · {candidate.name}</strong>
              <b>{candidate.score}</b>
              <span>{candidate.sector} · {fmtMoney(candidate.price)} · {candidate.action}</span>
              <span>模型分 {candidate.model_score} · 数据质量 {candidate.data_quality.toFixed(0)}% · {candidate.signal}</span>
              <span>{candidate.reference_source}</span>
              <p>{candidate.reason}</p>
              <button onClick={() => addStockToWatchlist(candidate.ticker)}>加入监控</button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>账户余额与仓位优化</h2>
            <p>按当前账户余额、持仓市值和风险纪律给出动态配仓方向。</p>
          </div>
          <span className="badge">{allocation ? fmtMoney(allocation.cash_balance) : "$0.00"} 现金</span>
        </div>
        {allocation && (
          <>
            <div className="allocation-summary">
              <strong>{allocation.cash_action}</strong>
              <span>账户 {fmtMoney(allocation.account_total)} · 目标现金 {fmtMoney(allocation.cash_target)}</span>
            </div>
            <div className="compact-table">
              {allocation.suggestions.map((item) => (
                <div key={item.ticker}>
                  <span>{item.ticker} · 当前 {item.current_weight.toFixed(2)}% / 目标 {item.target_weight.toFixed(2)}%</span>
                  <b>{item.action}</b>
                  <em>{fmtMoney(item.amount)}</em>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>模型验证与调教</h2>
            <p>点击“验证模型”后，用短期、中期、长期三段行情批量回测策略，并给出参数调教方向。</p>
          </div>
          <span className="badge">{validation.length ? `${validation.length} 个模型` : "等待验证"}</span>
        </div>
        <div className="advice-grid">
          {validation.map((item) => (
            <article key={item.strategy_id} className="advice-card">
              <strong>{item.strategy_id}</strong>
              <b>{pct(item.average_annual_return)}</b>
              <span>最佳 {item.best_ticker} · 加权回撤 {pct(item.average_max_drawdown)} · 真实数据 {item.valid_samples}/{item.tested}</span>
              <dl className="period-metrics">
                <div><dt>短期</dt><dd>{pct(item.short_return)} / {pct(item.short_drawdown)}</dd></div>
                <div><dt>中期</dt><dd>{pct(item.medium_return)} / {pct(item.medium_drawdown)}</dd></div>
                <div><dt>长期</dt><dd>{pct(item.long_return)} / {pct(item.long_drawdown)}</dd></div>
              </dl>
              <span className={item.data_quality >= 80 ? "quality-ok" : item.data_quality >= 50 ? "quality-warn" : "quality-risk"}>
                数据质量 {item.data_quality.toFixed(0)}% · {item.data_quality_label}
                {item.missing_samples ? ` · 缺失 ${item.missing_samples}` : ""}
              </span>
              <p>{item.tuning_note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>行情缓存</h2>
            <p>AKShare 可用时读取公开美股报价；不可用时回退到样例缓存，保证策略和 UI 可持续运行。</p>
          </div>
          <span className="badge">{quotes[0]?.source || "sample-fallback"}</span>
        </div>
        <div className="quote-grid">
          {quotes.map((quote) => (
            <article key={quote.ticker}>
              <strong>{quote.ticker}</strong>
              <b>{fmtMoney(quote.price)}</b>
              <span className={quote.pct_change < 0 ? "negative" : "positive"}>{pct(quote.pct_change)}</span>
              <small>{quote.source} · {quote.updated_at}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function GoldWatch({
  monitor,
  trades,
  loadGold,
  setNotice
}: {
  monitor: GoldMonitor;
  trades: GoldManualTrade[];
  loadGold: () => Promise<void>;
  setNotice: (notice: string) => void;
}) {
  const [tradeForm, setTradeForm] = useState({
    executed_at: currentLocalInputValue(),
    amount_cny: monitor.first_order_amount.toFixed(2),
    grams: "",
    price: monitor.live_price.toFixed(2),
    note: ""
  });

  const trend = useMemo(() => {
    const width = 720;
    const height = 260;
    const plot = { left: 58, right: 18, top: 18, bottom: 38 };
    const prices = monitor.trend_points.map((point) => point.price);
    const min = Math.min(...prices, monitor.day_low);
    const max = Math.max(...prices, monitor.day_high);
    const span = Math.max(max - min, 0.01);
    const plotWidth = width - plot.left - plot.right;
    const plotHeight = height - plot.top - plot.bottom;
    const points = monitor.trend_points.map((point, index) => {
      const x = plot.left + (index / Math.max(monitor.trend_points.length - 1, 1)) * plotWidth;
      const y = plot.top + ((max - point.price) / span) * plotHeight;
      return { ...point, x, y };
    });
    const yTicks = [max, (max + min) / 2, min].map((price) => ({
      price,
      y: plot.top + ((max - price) / span) * plotHeight,
    }));
    const xTicks = points.filter((_, index) => index === 0 || index === Math.floor(points.length / 2) || index === points.length - 1);
    return {
      width,
      height,
      min,
      max,
      line: points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" "),
      points,
      plot,
      yTicks,
      xTicks,
    };
  }, [monitor]);

  const plannedGrams = Number(tradeForm.grams) || (Number(tradeForm.amount_cny) && Number(tradeForm.price) ? Number(tradeForm.amount_cny) / Number(tradeForm.price) : 0);
  const totalGoldGrams = trades.reduce((sum, trade) => sum + (trade.side === "BUY" ? trade.grams : -trade.grams), 0);
  const totalGoldCost = trades.reduce((sum, trade) => sum + (trade.side === "BUY" ? trade.amount_cny : -trade.amount_cny), 0);
  const averageGoldCost = totalGoldGrams > 0 ? totalGoldCost / totalGoldGrams : 0;

  async function recordGoldTrade(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(tradeForm.amount_cny);
    const price = Number(tradeForm.price);
    const grams = tradeForm.grams ? Number(tradeForm.grams) : undefined;
    if (!amount || !price) {
      setNotice("请填写有效的黄金成交金额和成交价。");
      return;
    }
    await fetchJson<GoldManualTrade>("/gold/manual-trades", {
      method: "POST",
      body: JSON.stringify({
        side: "BUY",
        amount_cny: amount,
        grams,
        price,
        executed_at: tradeForm.executed_at.replace("T", " "),
        note: tradeForm.note
      })
    });
    setTradeForm((current) => ({ ...current, grams: "", note: "" }));
    await loadGold();
    setNotice("已记录一笔黄金线下买入，后续分析会纳入这笔成交。");
  }

  async function deleteGoldTrade(tradeId: string) {
    await fetchJson(`/gold/manual-trades/${tradeId}`, { method: "DELETE" });
    await loadGold();
    setNotice("已删除一笔黄金线下记录，持仓收益和策略建议已重算。");
  }

  return (
    <div className="page-grid gold-page">
      <Metric label="剩余资金" value={fmtCny(monitor.remaining_capital)} hint={`计划 ${fmtCny(monitor.planned_capital)} · 已投入 ${fmtCny(monitor.holding_cost)}`} tone="amber" icon={Coins} />
      <Metric label="实时金价" value={`¥${monitor.live_price.toFixed(2)}/克`} hint={`${monitor.trading_status} · ${monitor.quote_time}`} tone={monitor.pct_change < 0 ? "danger" : "green"} />
      <Metric label="持仓收益" value={fmtCny(monitor.holding_pnl)} hint={`${pct(monitor.holding_pnl_pct)} · 市值 ${fmtCny(monitor.holding_market_value)}`} tone={monitor.holding_pnl < 0 ? "danger" : "green"} />
      <Metric label="成本均价（元/克）" value={monitor.average_cost ? `¥${monitor.average_cost.toFixed(2)}` : "未持仓"} hint={`持仓 ${monitor.holding_grams.toFixed(4)} 克`} tone="amber" />

      <section className="panel wide gold-hero">
        <div className="panel-head">
          <div>
            <h2>民生积存金盯盘</h2>
            <p>{monitor.product_name} 当前按银行积存金公开分时价作为参考锚，剩余资金 {fmtCny(monitor.remaining_capital)}；系统只做盯盘和纪律分析，不自动交易。</p>
          </div>
          <div className="button-row">
            <span className="badge">{monitor.risk_level}</span>
            <button onClick={loadGold}>刷新黄金数据</button>
          </div>
        </div>
        <div className="gold-layout">
          <div className="gold-position">
            <span>当前金价</span>
            <strong>¥{monitor.live_price.toFixed(2)}/克</strong>
            <dl>
              <div><dt>今日涨跌</dt><dd>{monitor.change.toFixed(2)} / {pct(monitor.pct_change)}</dd></div>
              <div><dt>日内高低</dt><dd>{monitor.day_high.toFixed(2)} / {monitor.day_low.toFixed(2)}</dd></div>
              <div><dt>持仓收益</dt><dd>{fmtCny(monitor.holding_pnl)} / {pct(monitor.holding_pnl_pct)}</dd></div>
              <div><dt>成本均价</dt><dd>{monitor.average_cost ? `¥${monitor.average_cost.toFixed(2)}/克` : "未持仓"}</dd></div>
              <div><dt>买入规则</dt><dd>{fmtCny(monitor.min_purchase_amount)} 起，{fmtCny(monitor.increment_amount)} 递增</dd></div>
            </dl>
          </div>
          <div className="gold-advice">
            <span>当前建议</span>
            <strong>{monitor.action}</strong>
            <p>{monitor.advice}</p>
            <em>置信度 {Math.round(monitor.confidence * 100)}%</em>
          </div>
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>实时走势线</h2>
            <p>{monitor.reference_name} 分钟级走势；交易时段每 {monitor.refresh_seconds} 秒刷新一次，行情时间 {monitor.quote_time}。</p>
          </div>
          <span className="badge">{monitor.is_trading_session ? "交易时段" : "非交易时段"}</span>
        </div>
        <div className="gold-trend">
          <svg viewBox={`0 0 ${trend.width} ${trend.height}`} role="img" aria-label="民生积存金实时走势线">
            {trend.yTicks.map((tick) => (
              <g key={tick.price}>
                <line className="trend-grid" x1={trend.plot.left} x2={trend.width - trend.plot.right} y1={tick.y} y2={tick.y} />
                <text className="trend-y-label" x={8} y={tick.y + 4}>{tick.price.toFixed(2)}</text>
              </g>
            ))}
            <line className="trend-axis" x1={trend.plot.left} x2={trend.width - trend.plot.right} y1={trend.height - trend.plot.bottom} y2={trend.height - trend.plot.bottom} />
            {trend.xTicks.map((tick) => (
              <text className="trend-x-label" key={tick.time} x={tick.x} y={trend.height - 12}>{tick.time}</text>
            ))}
            <polyline className="trend-line" points={trend.line} />
            {trend.points.map((point) => (
              <g
                className="trend-point"
                key={`${point.time}-${point.price}`}
              >
                <circle className="trend-hit" cx={point.x} cy={point.y} r={14} />
                <circle className="trend-dot" cx={point.x} cy={point.y} r={point.time === "18:31" ? 5 : 3.5} />
                <g
                  className="trend-point-tooltip-svg"
                  transform={`translate(${point.x > trend.width - 140 ? point.x - 118 : point.x + 12}, ${point.y < 60 ? point.y + 16 : point.y - 50})`}
                >
                  <rect width="106" height="40" rx="7" />
                  <text x="10" y="16">{point.time}</text>
                  <text x="10" y="31">¥{point.price.toFixed(2)}/克</text>
                </g>
                <title>{`${point.time} · ¥${point.price.toFixed(2)}/克`}</title>
              </g>
            ))}
            {trend.points.length === 0 && (
              <text className="trend-empty-label" x={trend.width / 2} y={trend.height / 2}>
                暂无真实分时点
              </text>
            )}
          </svg>
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>线下操作记录</h2>
            <p>记录你在银行 App 实际成交的积存金，系统只使用真实输入，不自动补齐成交。</p>
          </div>
          <span className="badge">{trades.length ? `${trades.length} 笔记录` : "暂无记录"}</span>
        </div>
        <form className="gold-trade-form" onSubmit={recordGoldTrade}>
          <label>
            <span>成交时间</span>
            <input
              type="datetime-local"
              value={tradeForm.executed_at}
              onChange={(event) => setTradeForm((current) => ({ ...current, executed_at: event.target.value }))}
            />
          </label>
          <label>
            <span>买入金额</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={tradeForm.amount_cny}
              onChange={(event) => setTradeForm((current) => ({ ...current, amount_cny: event.target.value }))}
            />
          </label>
          <label>
            <span>成交价/克</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={tradeForm.price}
              onChange={(event) => setTradeForm((current) => ({ ...current, price: event.target.value }))}
            />
          </label>
          <label>
            <span>成交克数</span>
            <input
              type="number"
              min="0"
              step="0.0001"
              placeholder={plannedGrams ? plannedGrams.toFixed(4) : "可留空自动计算"}
              value={tradeForm.grams}
              onChange={(event) => setTradeForm((current) => ({ ...current, grams: event.target.value }))}
            />
          </label>
          <label className="wide-input">
            <span>备注</span>
            <input
              placeholder="例如：民生 App 手动买入"
              value={tradeForm.note}
              onChange={(event) => setTradeForm((current) => ({ ...current, note: event.target.value }))}
            />
          </label>
          <button type="submit">记录买入</button>
        </form>
        <div className="gold-trade-summary">
          <div><span>累计克数</span><strong>{totalGoldGrams.toFixed(4)} 克</strong></div>
          <div><span>累计投入</span><strong>{fmtCny(totalGoldCost)}</strong></div>
          <div><span>平均成本</span><strong>{averageGoldCost ? `¥${averageGoldCost.toFixed(2)}/克` : "未形成"}</strong></div>
          <div><span>按现价估值</span><strong>{fmtCny(totalGoldGrams * monitor.live_price)}</strong></div>
        </div>
        <div className="gold-trade-list">
          {trades.map((trade) => (
            <article key={trade.id}>
              <div>
                <strong>{trade.executed_at}</strong>
                <span>{trade.note || trade.product_name}</span>
              </div>
              <b>{trade.grams.toFixed(4)} 克</b>
              <span>{fmtCny(trade.amount_cny)} · ¥{trade.price.toFixed(2)}/克</span>
              <button type="button" onClick={() => deleteGoldTrade(trade.id)}>删除</button>
            </article>
          ))}
          {!trades.length && <p>还没有线下成交记录。你买入后在这里补一笔，系统就能按真实仓位分析。</p>}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>交易纪律</h2>
            <p>{monitor.settlement_rule}</p>
          </div>
          <span className="badge">{monitor.trade_rule}</span>
        </div>
        <div className="advice-grid">
          {monitor.watch_points.map((point) => (
            <article className="advice-card medium" key={point}>
              <strong>纪律检查</strong>
              <b>执行前确认</b>
              <p>{point}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>黄金参考指标</h2>
            <p>银行黄金报价以 App 最终确认为准；这里用截图价建立本地跟踪基准，后续可替换为民生接口适配器。</p>
          </div>
          <span className="badge">{monitor.reference_symbol}</span>
        </div>
        <div className="quote-grid">
          <article>
            <strong>{monitor.reference_name}</strong>
            <b>¥{monitor.reference_price.toFixed(2)}</b>
            <span className={monitor.reference_change_pct < 0 ? "negative" : "positive"}>{pct(monitor.reference_change_pct)}</span>
            <small>{monitor.reference_time}</small>
          </article>
          <article>
            <strong>首笔试探</strong>
            <b>{fmtCny(monitor.first_order_amount)}</b>
            <span>{monitor.first_order_grams.toFixed(4)} 克</span>
            <small>按当前价估算，成交以银行确认为准</small>
          </article>
          <article>
            <strong>剩余弹药</strong>
            <b>{fmtCny(monitor.reserve_cash)}</b>
            <span className="positive">用于后续价位台阶</span>
            <small>{monitor.source}</small>
          </article>
        </div>
      </section>
    </div>
  );
}

function Discipline({
  events,
  orders,
  holdings,
  selectedTicker,
  recordZaManualExecution,
  submitOfflineTrade,
  importUsmartScreenshot,
  importZaScreenshot
}: {
  events: DisciplineEvent[];
  orders: Order[];
  holdings: Holding[];
  selectedTicker: string;
  recordZaManualExecution: () => Promise<void>;
  submitOfflineTrade: (form: OfflineTradeForm) => Promise<void>;
  importUsmartScreenshot: () => Promise<void>;
  importZaScreenshot: () => Promise<void>;
}) {
  const [offlineTrade, setOfflineTrade] = useState<OfflineTradeForm>({
    broker: "za-bank",
    ticker: selectedTicker,
    side: "BUY",
    qty: "",
    price: "",
    executed_at: defaultExecutionTime(),
    note: ""
  });

  async function handleOfflineTradeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitOfflineTrade(offlineTrade);
    setOfflineTrade((current) => ({
      ...current,
      qty: "",
      price: "",
      note: "",
      executed_at: defaultExecutionTime()
    }));
  }

  return (
    <div className="page-grid">
      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>持仓纪律事件</h2>
            <p>买入理由、卖出条件、风险提醒和人工干预都必须落成记录。</p>
          </div>
          <span className="badge">{events.length} 条记录</span>
        </div>
        <div className="event-list">
          {events.map((event) => (
            <article className={`event ${event.severity}`} key={event.id}>
              <span />
              <div>
                <strong>{event.ticker} · {event.title}</strong>
                <p>{event.reason}</p>
                <small>{event.action} · {event.created_at}</small>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>执行记录</h2>
            <p>线下券商/App 已成交后，在这里回填，系统会写入本地订单和持仓。</p>
          </div>
          <button onClick={recordZaManualExecution}>记录 ZA 成交</button>
        </div>
        <form className="offline-trade-form" onSubmit={handleOfflineTradeSubmit}>
          <label>
            <span>券商</span>
            <select
              value={offlineTrade.broker}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, broker: event.target.value as OfflineTradeForm["broker"] }))}
            >
              <option value="za-bank">ZA Bank</option>
              <option value="usmart">uSMART</option>
              <option value="ibkr">IBKR</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            <span>股票</span>
            <input
              placeholder="NOK.US"
              value={offlineTrade.ticker}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))}
            />
          </label>
          <label>
            <span>方向</span>
            <select
              value={offlineTrade.side}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, side: event.target.value as OfflineTradeForm["side"] }))}
            >
              <option value="BUY">买入</option>
              <option value="SELL">卖出</option>
            </select>
          </label>
          <label>
            <span>数量</span>
            <input
              type="number"
              min="1"
              step="1"
              value={offlineTrade.qty}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, qty: event.target.value }))}
            />
          </label>
          <label>
            <span>成交价</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={offlineTrade.price}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, price: event.target.value }))}
            />
          </label>
          <label>
            <span>成交时间</span>
            <input
              type="datetime-local"
              value={offlineTrade.executed_at}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, executed_at: event.target.value }))}
            />
          </label>
          <label className="wide-input">
            <span>备注</span>
            <input
              placeholder="例如：ZA App 手动确认，按执行计划买入"
              value={offlineTrade.note}
              onChange={(event) => setOfflineTrade((current) => ({ ...current, note: event.target.value }))}
            />
          </label>
          <button type="submit">提交线下交易</button>
        </form>
        <div className="compact-table">
          {orders.map((order) => (
            <div key={order.id}>
              <span>{order.ticker}</span>
              <b>{order.qty} 股</b>
              <em>{order.order_type}</em>
            </div>
          ))}
        </div>
      </section>
      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>券商持仓对账</h2>
            <p>ZA Bank 和 uSMART 当前走结单、截图、CSV 或手工记录导入，系统统一生成本地持仓和 PnL。</p>
          </div>
          <div className="button-row">
            <button onClick={importZaScreenshot}>导入 ZA 截图</button>
            <button onClick={importUsmartScreenshot}>导入 uSMART 截图</button>
          </div>
        </div>
        <table>
          <thead>
            <tr><th>券商</th><th>股票</th><th>数量</th><th>成本</th><th>现价</th><th>市值</th><th>盈亏</th><th>更新时间</th></tr>
          </thead>
          <tbody>
            {holdings.map((holding) => (
              <tr key={`${holding.broker}-${holding.ticker}`}>
                <td>{holding.broker}</td>
                <td><b>{holding.ticker}</b></td>
                <td>{holding.qty}</td>
                <td>{fmtMoney(holding.avg_cost)}</td>
                <td>{fmtMoney(holding.market_price)}</td>
                <td>{fmtMoney(holding.market_value)}</td>
                <td className={holding.pnl < 0 ? "negative" : "positive"}>{fmtMoney(holding.pnl)}</td>
                <td>{holding.updated_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Analysis(props: {
  strategies: StrategyModel[];
  watchlist: WatchlistItem[];
  backtest: BacktestResult | null;
  bestStrategy?: StrategyModel;
  selectedStrategy: string;
  selectedTicker: string;
  analysisType: string;
  setSelectedStrategy: (value: string) => void;
  setSelectedTicker: (value: string) => void;
  setAnalysisType: (value: string) => void;
  runBacktest: () => Promise<void>;
  importPreviousCloseAndBacktest: () => Promise<void>;
}) {
  const result = props.backtest;
  return (
    <div className="page-grid">
      <Metric label="最佳模型" value={props.bestStrategy?.name || "PE_v1"} hint={`综合评分 ${props.bestStrategy?.score || 91}`} tone="green" />
      <Metric label="策略数量" value={`${props.strategies.length}`} hint="运行中 3 / 回测 4" />
      <Metric label="最高年化" value={props.bestStrategy ? pct(props.bestStrategy.annual_return) : "+28.4%"} hint="回测模式" tone="green" />
      <Metric label="干预机会成本" value="$18,420" hint="近 90 天少赚估算" tone="amber" />

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>本地模型评测</h2>
            <p>本地评测使用当前规则、样例行情和已记录交易生成，用于先验证模型体验。</p>
          </div>
          <div className="segmented">
            <button>回测</button>
            <button className="selected">线下记录</button>
            <button>实盘预留</button>
          </div>
        </div>
        <div className="analysis-form">
          <label>策略模型
            <select value={props.selectedStrategy} onChange={(event) => props.setSelectedStrategy(event.target.value)}>
              {props.strategies.map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.name} 纪律策略</option>)}
            </select>
          </label>
          <label>股票
            <select value={props.selectedTicker} onChange={(event) => props.setSelectedTicker(event.target.value)}>
              {props.watchlist.map((item) => <option key={item.ticker} value={item.ticker}>{item.ticker} · {item.name}</option>)}
            </select>
          </label>
          <label>评测类型
            <select value={props.analysisType} onChange={(event) => props.setAnalysisType(event.target.value)}>
              <option value="offline">线下记录</option>
              <option value="backtest">回测</option>
              <option value="paper">实盘预留</option>
            </select>
          </label>
          <label>开始日期<input value="2026-05-01" readOnly /></label>
          <label>结束日期<input value="2026-07-16" readOnly /></label>
          <button className="primary" onClick={props.runBacktest}>运行评测</button>
          <button onClick={props.importPreviousCloseAndBacktest}>导入昨收并评测</button>
        </div>

        {result && (
          <div className="result-grid">
            <Metric label="年化收益" value={pct(result.annual_return)} hint="样例回放" tone="green" />
            <Metric label="累计盈利" value={fmtMoney(result.pnl)} hint="" tone="green" />
            <Metric label="胜率" value={`${Math.round(result.win_rate * 100)}%`} hint="" />
            <Metric label="盈亏比" value={result.profit_factor.toFixed(1)} hint="" />
            <Metric label="最大回撤" value={pct(result.max_drawdown)} hint="" tone="danger" />
            <Metric label="交易次数" value={`${result.trades}`} hint="" />
            <Metric label="SPY 基准" value={pct(result.benchmark_return)} hint="" />
            <Metric label="成交记录" value="2" hint="" />
          </div>
        )}
      </section>

      <section className="panel wide">
        <div className="panel-head">
          <div>
            <h2>多策略收益分析</h2>
            <p>深色曲线模拟模型表现，灰色曲线模拟 SPY 基准。</p>
          </div>
          <div className="segmented"><button className="selected">月收益率</button><button>周收益率</button><button>年收益率</button></div>
        </div>
        <div className="chart" aria-label="模型收益曲线">
          {result?.records.map((point, index) => (
            <i
              key={point.date}
              style={{
                left: `${8 + index * 14}%`,
                bottom: `${18 + (point.equity - 100000) / 1400}%`
              }}
              title={`${point.date} ${point.equity}`}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
