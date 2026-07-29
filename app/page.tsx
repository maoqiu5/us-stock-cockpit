"use client";

import {
  Activity,
  BarChart3,
  Bot,
  CirclePause,
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
const LEGACY_APP_PASSWORD_STORAGE_KEY = "us-stock-cockpit-password";
const LEGACY_APP_USERNAME_STORAGE_KEY = "us-stock-cockpit-username";

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
  watch_score: number;
  watch_label: string;
  watch_reason: string;
  entry_low_price: number;
  entry_high_price: number;
  chase_limit_price: number;
  stop_loss_price: number;
  take_profit_price: number;
  max_loss_amount: number;
  quote_source: string;
  quote_updated_at: string;
  data_status: string;
  volume_score: number;
  ma5: number;
  ma20: number;
  distance_to_20d_high_pct: number;
  distance_to_20d_low_pct: number;
  atr20: number;
  relative_volume: number;
  vwap_hint: number;
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
  account_name: string;
  account_total: number;
  available_cash: number;
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
  entry_low_price: number;
  entry_high_price: number;
  chase_limit_price: number;
  max_loss_amount: number;
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
  liquidity_score: number;
  dollar_volume: number;
  market_cap: number;
  exchange: string;
  source_updated_at: string;
  data_status: string;
};

type AllocationSuggestion = {
  ticker: string;
  broker: string;
  account_name: string;
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

type DisciplineNotification = {
  id: string;
  title: string;
  detail: string;
  severity: "info" | "warn" | "risk";
  created_at: string;
};

type DataAssetSummary = {
  name: string;
  count: number;
  latest: string;
  status: string;
};

type PostMarketReview = {
  as_of: string;
  snapshot_source: string;
  watchlist_count: number;
  candidate_count: number;
  trade_actions: number;
  risk_items: string[];
  next_day_focus: string[];
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

type SubmitFeedback = {
  tone: "success" | "error" | "info";
  title: string;
  detail: string;
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
  notifications: DisciplineNotification[];
  dataAssets: DataAssetSummary[];
  dailyReview: PostMarketReview | null;
};

const nav = [
  { id: "dashboard", label: "驾驶舱", key: "D", icon: Gauge },
  { id: "strategies", label: "策略模型", key: "S", icon: SlidersHorizontal },
  { id: "watchlist", label: "股票池", key: "W", icon: Layers3 },
  { id: "discipline", label: "持仓纪律", key: "H", icon: ShieldCheck },
  { id: "analysis", label: "模型分析", key: "A", icon: BarChart3 }
] as const;

const fmtMoney = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);

const roundMoney = (value: number) => Math.round(value * 100) / 100;

const pct = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;

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
  const controller = timeoutMs ? new AbortController() : null;
  const timeout = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller?.signal || init?.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      },
      cache: "no-store",
      credentials: "same-origin"
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
        message = "需要登录门户";
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
    notifications: [],
    dataAssets: [],
    dailyReview: null
  });
  const [newTicker, setNewTicker] = useState("");
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [validation, setValidation] = useState<ModelValidationItem[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("pe_v1");
  const [selectedTicker, setSelectedTicker] = useState("NOK.US");
  const [analysisType, setAnalysisType] = useState("offline");
  const [preparedOrder, setPreparedOrder] = useState<PreparedOrder | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [validatingModels, setValidatingModels] = useState(false);
  const [notice, setNotice] = useState("");
  const [submitFeedback, setSubmitFeedback] = useState<SubmitFeedback | null>(null);
  const [marketSession, setMarketSession] = useState(() => getUSMarketSession());
  const loadingRef = useRef(false);

  function showFeedback(tone: SubmitFeedback["tone"], title: string, detail: string) {
    setNotice(detail);
    setSubmitFeedback({ tone, title, detail });
  }

  function showOperationError(error: unknown, title: string, fallback: string) {
    showFeedback("error", title, error instanceof Error ? error.message : fallback);
  }

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const [summary, strategies, events, orders, risk, brokers, execution, sources, holdings, accountBalances, allocation, notifications, dataAssets, dailyReview] = await Promise.all([
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
        fetchJson<PortfolioOptimization>("/portfolio/optimization"),
        fetchJson<DisciplineNotification[]>("/notifications"),
        fetchJson<DataAssetSummary[]>("/data-assets/summary"),
        fetchJson<PostMarketReview>("/daily-review")
      ]);
      setData((current) => ({ ...current, summary, strategies, events, orders, risk, brokers, execution, sources, holdings, accountBalances, allocation, notifications, dataAssets, dailyReview }));
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
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    window.localStorage.removeItem(LEGACY_APP_USERNAME_STORAGE_KEY);
    window.localStorage.removeItem(LEGACY_APP_PASSWORD_STORAGE_KEY);
    load().catch((error) => {
      setLoading(false);
      if (error instanceof Error && error.message === "需要登录门户") {
        window.location.assign("/?returnTo=/usstock");
        return;
      }
      setNotice("后端暂未连接，正在显示前端骨架。");
    });
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => setMarketSession(getUSMarketSession()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const refreshSeconds = marketSession.isOpen ? 60 : 0;
    if (!refreshSeconds) return undefined;
    load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    const timer = window.setInterval(() => {
      load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    }, refreshSeconds * 1000);
    return () => window.clearInterval(timer);
  }, [load, marketSession.isOpen]);

  useEffect(() => {
    runBacktest().catch(() => undefined);
  }, []);

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
      showOperationError(error, "回测失败", "缺少真实历史数据，无法回测。");
    }
  }

  async function toggleAutomation(paused: boolean) {
    try {
      await fetchJson(paused ? "/automation/resume" : "/automation/pause", { method: "POST" });
      await load();
      showFeedback("success", "状态已更新", paused ? "已恢复自动执行监控。" : "已暂停自动执行监控。");
    } catch (error) {
      showOperationError(error, "状态更新失败", "自动执行状态更新失败，请稍后重试。");
    }
  }

  async function previewUsmartOrder() {
    try {
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
      showFeedback("success", "预览已生成", `${selectedTicker} 的 uSMART 订单预览已生成。`);
    } catch (error) {
      showOperationError(error, "预览失败", "订单预览失败，请稍后重试。");
    }
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
      showFeedback("error", "提交失败", "请填写有效的股票代码、数量和成交价。");
      throw new Error("请填写有效的股票代码、数量和成交价。");
    }
    try {
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
      showFeedback("success", "线下交易已提交", `已记录 ${ticker} ${form.side === "BUY" ? "买入" : "卖出"} ${qty} 股，并刷新本地持仓。`);
    } catch (error) {
      showOperationError(error, "提交失败", "线下交易提交失败，请稍后重试。");
      throw error;
    }
  }

  async function updateAccountCash(broker: AccountBalance["broker"], availableCash: number) {
    if (!Number.isFinite(availableCash) || availableCash < 0) {
      showFeedback("error", "保存失败", "请填写有效的账户可用现金。");
      throw new Error("请填写有效的账户可用现金。");
    }
    try {
      await fetchJson<AccountBalance>(`/portfolio/account-balances/${encodeURIComponent(broker)}`, {
        method: "POST",
        body: JSON.stringify({ available_cash: availableCash, note: "股票池手动设置" })
      });
      await load();
      showFeedback("success", "现金已保存", `已更新 ${broker} 可用现金 ${fmtMoney(availableCash)}。`);
    } catch (error) {
      showOperationError(error, "保存失败", "账户可用现金保存失败，请稍后重试。");
      throw error;
    }
  }

  async function deleteManualExecution(order: Order) {
    if (order.order_type !== "MANUAL") {
      showFeedback("error", "撤回失败", "只能删除线下手工交易记录。");
      return;
    }
    const confirmed = window.confirm(`确认撤回 ${order.ticker} ${order.side} ${order.qty} 股这条线下交易记录吗？系统会同步回滚本地现金和持仓。`);
    if (!confirmed) return;
    try {
      const result = await fetchJson<{ deleted: string; holding_note: string; events_removed: string }>(`/manual-executions/${encodeURIComponent(order.id)}`, { method: "DELETE" });
      await load();
      showFeedback("success", "线下交易已撤回", `已撤回 ${result.deleted}。${result.holding_note}`);
    } catch (error) {
      showOperationError(error, "撤回失败", "线下交易撤回失败，请稍后重试。");
    }
  }

  async function importUsmartScreenshot() {
    try {
      const result = await fetchJson<USmartScreenshotResult>("/imports/usmart-screenshot", {
        method: "POST",
        body: JSON.stringify({
          image_path: USMART_SCREENSHOT_PATH,
          as_of: "07/16 14:02"
        })
      });
      await load();
      setActive("discipline");
      showFeedback("success", "uSMART 导入成功", `已从 uSMART 截图导入 ${result.imported_holdings} 条持仓，净资产 ${fmtMoney(result.net_asset)}。`);
    } catch (error) {
      showOperationError(error, "uSMART 导入失败", "uSMART 截图导入失败，请检查图片路径或稍后重试。");
    }
  }

  async function importZaScreenshot() {
    try {
      const result = await fetchJson<ZABankScreenshotResult>("/imports/za-screenshot", {
        method: "POST",
        body: JSON.stringify({
          image_path: ZA_SCREENSHOT_PATH,
          as_of: "07/16 14:04"
        })
      });
      await load();
      setActive("discipline");
      showFeedback("success", "ZA Bank 导入成功", `已从 ZA Bank 截图导入 ${result.imported_holdings} 条持仓。`);
    } catch (error) {
      showOperationError(error, "ZA Bank 导入失败", "ZA Bank 截图导入失败，请检查图片路径或稍后重试。");
    }
  }

  async function importPreviousClose() {
    try {
      const result = await fetchJson<PreviousCloseImportResult>("/market/import-previous-close", { method: "POST" });
      await load();
      showFeedback("success", "昨收已导入", `已导入 ${result.imported} 条上一交易日收盘价，账户估值 ${fmtMoney(result.account_total)}，持仓盈亏 ${fmtMoney(result.total_pnl)}。`);
      return result;
    } catch (error) {
      showOperationError(error, "昨收导入失败", "上一交易日收盘价导入失败，请稍后重试。");
      throw error;
    }
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
      showFeedback("success", "已加入股票池", `${added.ticker} 已加入股票池，并已用最新可用行情更新趋势与信号。`);
    } catch (error) {
      showOperationError(error, "加入失败", "加入失败，请稍后重试。");
    }
  }

  async function deleteWatchlistTicker(ticker: string) {
    try {
      await fetchJson(`/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
      await load();
      showFeedback("success", "已删除股票", `${ticker} 已从股票池删除。`);
    } catch (error) {
      showOperationError(error, "删除失败", `${ticker} 删除失败，请稍后重试。`);
    }
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
      showFeedback("success", "模型验证完成", `已验证 ${result.length} 个策略模型、${tested} 个股票样本，模型分已更新到股票池和持仓建议。`);
    } catch (error) {
      showOperationError(error, "模型验证失败", "模型验证失败，请稍后重试。");
    } finally {
      setValidatingModels(false);
    }
  }

  async function createDailySnapshot() {
    try {
      const result = await fetchJson<{ as_of: string; watchlist_count: number; candidate_count: number; trade_actions: number; saved: boolean }>("/daily-snapshot", { method: "POST" });
      await load();
      showFeedback("success", "快照已生成", `已生成今日快照：股票池 ${result.watchlist_count} 个，候选股 ${result.candidate_count} 个，动作 ${result.trade_actions} 个。`);
    } catch (error) {
      showOperationError(error, "快照生成失败", "今日快照生成失败，请稍后重试。");
    }
  }

  async function logoutPortal() {
    try {
      await fetch("/logout", { method: "POST", credentials: "same-origin" });
    } finally {
      window.location.assign("/");
    }
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
            <div><dt>同步状态</dt><dd>{data.summary?.sync_status || "门户已认证"}</dd></div>
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
            <button className="sync" type="button" onClick={logoutPortal}>
              <LogOut size={15} />
              退出门户
            </button>
            <button className="sync" onClick={() => data.summary && toggleAutomation(data.summary.automation_paused)}>
              {data.summary?.automation_paused ? <Play size={15} /> : <CirclePause size={15} />}
              {data.summary?.automation_paused ? "恢复自动执行" : "暂停自动执行"}
            </button>
          </div>
        </header>

        {notice && <div className="notice">{notice}</div>}
        {submitFeedback && (
          <div className={`submit-feedback ${submitFeedback.tone}`} role="status" aria-live="polite">
            <div>
              <strong>{submitFeedback.title}</strong>
              <p>{submitFeedback.detail}</p>
            </div>
            <button type="button" onClick={() => setSubmitFeedback(null)}>关闭</button>
          </div>
        )}
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
            notifications={data.notifications}
            dataAssets={data.dataAssets}
            dailyReview={data.dailyReview}
            validation={validation}
            newTicker={newTicker}
            setNewTicker={setNewTicker}
            addStockToWatchlist={addStockToWatchlist}
            deleteWatchlistTicker={deleteWatchlistTicker}
            load={load}
            importPreviousClose={importPreviousClose}
            validateModels={validateModels}
            createDailySnapshot={createDailySnapshot}
            validatingModels={validatingModels}
            submitOfflineTrade={submitOfflineTrade}
            updateAccountCash={updateAccountCash}
          />
        )}
        {active === "discipline" && (
          <Discipline
            events={data.events}
            orders={data.orders}
            holdings={data.holdings}
            selectedTicker={selectedTicker}
            recordZaManualExecution={recordZaManualExecution}
            submitOfflineTrade={submitOfflineTrade}
            deleteManualExecution={deleteManualExecution}
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
  notifications,
  dataAssets,
  dailyReview,
  validation,
  newTicker,
  setNewTicker,
  addStockToWatchlist,
  deleteWatchlistTicker,
  load,
  importPreviousClose,
  validateModels,
  createDailySnapshot,
  validatingModels,
  submitOfflineTrade,
  updateAccountCash
}: {
  items: WatchlistItem[];
  quotes: MarketQuote[];
  holdings: Holding[];
  accountBalances: AccountBalance[];
  tradePlan: TradePlanItem[];
  candidates: CandidateStock[];
  allocation: PortfolioOptimization | null;
  notifications: DisciplineNotification[];
  dataAssets: DataAssetSummary[];
  dailyReview: PostMarketReview | null;
  validation: ModelValidationItem[];
  newTicker: string;
  setNewTicker: (value: string) => void;
  addStockToWatchlist: (ticker: string) => Promise<void>;
  deleteWatchlistTicker: (ticker: string) => Promise<void>;
  load: () => Promise<void>;
  importPreviousClose: () => Promise<PreviousCloseImportResult>;
  validateModels: () => Promise<void>;
  createDailySnapshot: () => Promise<void>;
  validatingModels: boolean;
  submitOfflineTrade: (form: OfflineTradeForm) => Promise<void>;
  updateAccountCash: (broker: AccountBalance["broker"], availableCash: number) => Promise<void>;
}) {
  const [tradeDraft, setTradeDraft] = useState<OfflineTradeForm | null>(null);
  const [cashDraft, setCashDraft] = useState<{ broker: AccountBalance["broker"]; value: string } | null>(null);
  const quoteMap = new Map(quotes.map((quote) => [quote.ticker, quote]));
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
  const accountTotalByBroker = new Map(accountBalances.map((account) => [account.broker, account.account_total]));
  const holdingMap = new Map<string, { value: number; brokers: Set<string>; rows: Holding[] }>();
  holdings.forEach((holding) => {
    const current = holdingMap.get(holding.ticker) || { value: 0, brokers: new Set<string>(), rows: [] };
    current.value += holding.market_value;
    current.brokers.add(holding.broker);
    current.rows.push(holding);
    holdingMap.set(holding.ticker, current);
  });
  const sortedWatchlistItems = [...items].sort((left, right) => {
    const leftHolding = holdingMap.get(left.ticker);
    const rightHolding = holdingMap.get(right.ticker);
    if (leftHolding && rightHolding) return rightHolding.value - leftHolding.value;
    if (leftHolding) return -1;
    if (rightHolding) return 1;
    return 0;
  });

  function openTradeModal(item: WatchlistItem, side: OfflineTradeForm["side"] = "BUY", broker?: OfflineTradeForm["broker"]) {
    const quote = quoteMap.get(item.ticker);
    const plan = tradePlan.find((row) => row.ticker === item.ticker && (broker ? row.broker === broker : true));
    const preferredBroker = (broker || plan?.broker || accountBalances[0]?.broker || "za-bank") as OfflineTradeForm["broker"];
    const referencePrice = side === "BUY"
      ? (plan?.entry_high_price || item.entry_high_price || quote?.price || plan?.reference_price || 0)
      : (plan?.reference_price || quote?.price || item.take_profit_price || 0);
    setTradeDraft({
      broker: preferredBroker,
      ticker: item.ticker,
      side,
      qty: "",
      price: referencePrice ? String(roundMoney(referencePrice)) : "",
      executed_at: defaultExecutionTime(),
      note: "股票池中长线纪律记录"
    });
  }

  async function handleTradeDraftSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tradeDraft) return;
    try {
      await submitOfflineTrade(tradeDraft);
      setTradeDraft(null);
    } catch {
      // Keep the modal open so the user can correct and resubmit.
    }
  }

  async function handleCashDraftSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cashDraft) return;
    try {
      await updateAccountCash(cashDraft.broker, Number(cashDraft.value));
      setCashDraft(null);
    } catch {
      // Keep the modal open so the user can correct and resubmit.
    }
  }

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
            <button onClick={createDailySnapshot}>生成今日快照</button>
          </div>
        </div>
        <div className="ops-insight-grid">
          <article className="ops-insight-card">
            <header><ShieldCheck size={16} /><strong>纪律通知</strong></header>
            {notifications.slice(0, 3).map((item) => (
              <p key={item.id} className={`ops-${item.severity}`}><b>{item.title}</b><span>{item.detail}</span></p>
            ))}
          </article>
          <article className="ops-insight-card">
            <header><Database size={16} /><strong>本地数据资产</strong></header>
            {dataAssets.map((item) => (
              <p key={item.name}><b>{item.name}</b><span>{item.count} 份 · {item.latest || item.status}</span></p>
            ))}
          </article>
          <article className="ops-insight-card">
            <header><Radar size={16} /><strong>盘后复盘</strong></header>
            {dailyReview ? (
              <>
                <p><b>{dailyReview.snapshot_source}</b><span>{dailyReview.watchlist_count} 股 · {dailyReview.trade_actions} 个动作</span></p>
                <p><b>明日重点</b><span>{dailyReview.next_day_focus[0] || "暂无强动作，继续观察。"}</span></p>
              </>
            ) : (
              <p><b>暂无复盘</b><span>生成今日快照后会保留本地复盘依据。</span></p>
            )}
          </article>
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
              <button type="button" onClick={() => setCashDraft({ broker: account.broker, value: String(account.available_cash) })}>调整现金</button>
            </article>
          ))}
        </div>
        <div className="watchlist-priority-grid">
          <section className="decision-panel">
            <div className="panel-head compact-head">
              <div>
                <h2>今日配舱策略</h2>
                <p>按账户现金弹药、8% 现金垫、股票池信号和中长线目标仓位生成今日加仓/减仓建议。</p>
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
                      <div key={`deck-buy-${item.broker}-${item.ticker}`}>
                        <span>{item.account_name || item.broker} · {item.ticker} · 买入 {item.entry_low_price && item.entry_high_price ? `${fmtMoney(item.entry_low_price)}-${fmtMoney(item.entry_high_price)}` : fmtMoney(item.reference_price)} · 追高线 {item.chase_limit_price ? fmtMoney(item.chase_limit_price) : "-"} · 止损 {fmtMoney(item.stop_loss_price)}</span>
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
                      <div key={`deck-sell-${item.broker}-${item.ticker}`}>
                        <span>{item.account_name || item.broker} · {item.ticker} · 卖出参考 {fmtMoney(item.reference_price)} · 风控止损 {fmtMoney(item.stop_loss_price)} · 反弹目标 {fmtMoney(item.take_profit_price)}</span>
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
            {allocation && (
              <div className="allocation-inline">
                <div>
                  <span>仓位优化依据</span>
                  <strong>{allocation.cash_action}</strong>
                  <small>账户 {fmtMoney(allocation.account_total)} · 当前现金 {fmtMoney(allocation.cash_balance)} · 目标现金 {fmtMoney(allocation.cash_target)}</small>
                </div>
                <div className="compact-table">
                  {allocation.suggestions.slice(0, 4).map((item) => (
                    <div key={`${item.broker}-${item.ticker}`}>
                      <span>{item.account_name || item.broker} · {item.ticker} · 当前 {item.current_weight.toFixed(2)}% / 目标 {item.target_weight.toFixed(2)}%</span>
                      <b>{item.action}</b>
                      <em>{fmtMoney(item.amount)}</em>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
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
            <tr><th>股票</th><th>现价</th><th>涨跌</th><th>数据</th><th>持仓</th><th>成本</th><th>持仓盈亏</th><th>仓位</th><th>趋势</th><th>中长线策略</th><th>纪律价</th><th>操作</th></tr>
          </thead>
          <tbody>
            {sortedWatchlistItems.map((item) => {
              const quote = quoteMap.get(item.ticker);
              const holding = holdingMap.get(item.ticker);
              const hasModelValidation = item.model_reason && item.model_reason !== "尚未验证模型";
              return (
                <tr key={item.ticker}>
                  <td><b>{item.ticker}</b><span>{holding ? `${Array.from(holding.brokers).join(" / ")} · ${item.name}` : item.name}</span></td>
                  <td>{quote ? fmtMoney(quote.price) : "-"}</td>
                  <td className={quote && quote.pct_change < 0 ? "negative" : "positive"}>{quote ? pct(quote.pct_change) : "-"}</td>
                  <td className="source-cell">
                    <b>{item.data_status || quote?.source || "-"}</b>
                    <span>{item.quote_updated_at || quote?.updated_at || "-"}</span>
                  </td>
                  <td>
                    {holding ? (
                      <div className="account-holding-list">
                        {holding.rows.map((row) => <span key={`${row.broker}-qty`}>{row.broker} · {row.qty.toFixed(row.qty < 1 ? 4 : 2)}</span>)}
                      </div>
                    ) : "-"}
                  </td>
                  <td>
                    {holding ? (
                      <div className="account-holding-list">
                        {holding.rows.map((row) => <span key={`${row.broker}-cost`}>{row.broker} · {fmtMoney(row.avg_cost)}</span>)}
                      </div>
                    ) : "-"}
                  </td>
                  <td>
                    {holding ? (
                      <div className="account-holding-list">
                        {holding.rows.map((row) => {
                          const cost = row.avg_cost * row.qty;
                          const pnlPct = cost ? (row.pnl / cost) * 100 : 0;
                          return <span key={`${row.broker}-pnl`} className={row.pnl < 0 ? "negative" : "positive"}>{row.broker} · {fmtMoney(row.pnl)} / {pct(pnlPct)}</span>;
                        })}
                      </div>
                    ) : "-"}
                  </td>
                  <td>
                    {holding ? (
                      <div className="account-holding-list">
                        {holding.rows.map((row) => {
                          const total = accountTotalByBroker.get(row.broker) || row.market_value;
                          return <span key={`${row.broker}-weight`}>{row.broker} · {pct((row.market_value / Math.max(total, 1)) * 100)}</span>;
                        })}
                      </div>
                    ) : "-"}
                  </td>
                  <td>{item.trend}</td>
                  <td className="model-cell">
                    {item.watch_score || "-"}
                    <span>{item.watch_label || "-"}</span>
                    <span>{holding ? `${item.signal} · 分账户纪律` : item.signal}</span>
                    <span>{hasModelValidation ? `模型分 ${item.model_score} · ${item.model_reason}` : item.signal_reason || item.watch_reason || "点击验证模型后生成"}</span>
                    <span>{item.ma5 && item.ma20 ? `MA5/20 ${item.ma5}/${item.ma20} · ATR ${item.atr20 || "-"}` : "日线缓存不足"}</span>
                  </td>
                  <td className="source-cell">
                    <b>{item.entry_low_price && item.entry_high_price ? `${fmtMoney(item.entry_low_price)}-${fmtMoney(item.entry_high_price)}` : "不追"}</b>
                    <span>追高 {item.chase_limit_price ? fmtMoney(item.chase_limit_price) : "-"} · 止损 {item.stop_loss_price ? fmtMoney(item.stop_loss_price) : "-"}</span>
                  </td>
                  <td>
                    {holding ? (
                      <div className="row-action-stack">
                        <span>持仓中</span>
                        <button type="button" onClick={() => openTradeModal(item, "BUY")}>记录交易</button>
                      </div>
                    ) : (
                      <div className="row-action-stack">
                        <button type="button" onClick={() => openTradeModal(item, "BUY")}>记录交易</button>
                        <button onClick={() => deleteWatchlistTicker(item.ticker)}>删除</button>
                      </div>
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
            <article key={`${item.broker}-${item.ticker}`} className={`execution-plan-card ${item.side.toLowerCase()}`}>
              <header>
                <strong>{item.ticker}</strong>
                <b>{item.action}</b>
                <span>{item.account_name || item.broker} · {item.signal} · 模型分 {item.model_score || "-"}</span>
              </header>
              <dl>
                <div><dt>方向</dt><dd>{item.side === "NONE" ? "不下单" : item.side}</dd></div>
                <div><dt>建议股数</dt><dd>{item.suggested_qty}</dd></div>
                <div><dt>金额差</dt><dd>{fmtMoney(item.delta_amount)}</dd></div>
                <div><dt>参考价</dt><dd>{fmtMoney(item.reference_price)}</dd></div>
                <div><dt>账户现金</dt><dd>{fmtMoney(item.available_cash)}</dd></div>
                <div><dt>账户仓位</dt><dd>{item.current_weight.toFixed(2)}% → {item.target_weight.toFixed(2)}%</dd></div>
                <div><dt>买入区间</dt><dd>{item.entry_low_price && item.entry_high_price ? `${fmtMoney(item.entry_low_price)}-${fmtMoney(item.entry_high_price)}` : "不追"}</dd></div>
                <div><dt>追高线</dt><dd>{item.chase_limit_price ? fmtMoney(item.chase_limit_price) : "-"}</dd></div>
                <div><dt>止损/止盈</dt><dd>{fmtMoney(item.stop_loss_price)} / {fmtMoney(item.take_profit_price)}</dd></div>
                <div><dt>最大亏损</dt><dd>{item.max_loss_amount ? fmtMoney(item.max_loss_amount) : "-"}</dd></div>
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
            <h2>中长期候选股发现</h2>
            <p>用于寻找值得长期跟踪的标的，先看质量、估值、趋势和真实数据质量，再决定是否加入股票池。</p>
          </div>
          <span className="badge">{candidates.length} 个候选</span>
        </div>
        <div className="advice-grid">
          {candidates.map((candidate) => (
            <article key={candidate.ticker} className="advice-card">
              <strong>{candidate.ticker} · {candidate.name}</strong>
              <b>{candidate.score}</b>
              <span>{candidate.sector} · {fmtMoney(candidate.price)} · {candidate.action}</span>
              <span>模型分 {candidate.model_score} · 数据质量 {candidate.data_quality.toFixed(0)}% · 流动性 {candidate.liquidity_score || "-"}</span>
              <span>{candidate.exchange || "US"} · 成交额 {candidate.dollar_volume ? fmtMoney(candidate.dollar_volume) : "-"} · 市值 {candidate.market_cap ? fmtMoney(candidate.market_cap) : "-"}</span>
              <span>{candidate.data_status || "真实扫描"} · {candidate.source_updated_at || "-"} · {candidate.reference_source}</span>
              <p>{candidate.reason}</p>
              <button onClick={() => addStockToWatchlist(candidate.ticker)}>加入监控</button>
            </article>
          ))}
        </div>
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

      {tradeDraft && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <form className="inline-modal" onSubmit={handleTradeDraftSubmit}>
            <header>
              <strong>{tradeDraft.ticker} 线下交易记录</strong>
              <button type="button" onClick={() => setTradeDraft(null)}>关闭</button>
            </header>
            <div className="offline-trade-form">
              <label>
                <span>券商</span>
                <select value={tradeDraft.broker} onChange={(event) => setTradeDraft((current) => current ? { ...current, broker: event.target.value as OfflineTradeForm["broker"] } : current)}>
                  <option value="za-bank">ZA Bank</option>
                  <option value="usmart">uSMART</option>
                  <option value="ibkr">IBKR</option>
                  <option value="other">其他</option>
                </select>
              </label>
              <label>
                <span>方向</span>
                <select value={tradeDraft.side} onChange={(event) => setTradeDraft((current) => current ? { ...current, side: event.target.value as OfflineTradeForm["side"] } : current)}>
                  <option value="BUY">买入</option>
                  <option value="SELL">卖出</option>
                </select>
              </label>
              <label>
                <span>数量</span>
                <input type="number" min="0.0001" step="0.0001" value={tradeDraft.qty} onChange={(event) => setTradeDraft((current) => current ? { ...current, qty: event.target.value } : current)} />
              </label>
              <label>
                <span>成交价</span>
                <input type="number" min="0" step="0.01" value={tradeDraft.price} onChange={(event) => setTradeDraft((current) => current ? { ...current, price: event.target.value } : current)} />
              </label>
              <label>
                <span>成交时间</span>
                <input type="datetime-local" value={tradeDraft.executed_at} onChange={(event) => setTradeDraft((current) => current ? { ...current, executed_at: event.target.value } : current)} />
              </label>
              <label className="wide-input">
                <span>备注</span>
                <input value={tradeDraft.note} onChange={(event) => setTradeDraft((current) => current ? { ...current, note: event.target.value } : current)} />
              </label>
            </div>
            <div className="button-row">
              <button type="button" onClick={() => setTradeDraft(null)}>取消</button>
              <button type="submit" className="primary">提交并刷新</button>
            </div>
          </form>
        </div>
      )}

      {cashDraft && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <form className="inline-modal compact" onSubmit={handleCashDraftSubmit}>
            <header>
              <strong>{cashDraft.broker} 可用现金</strong>
              <button type="button" onClick={() => setCashDraft(null)}>关闭</button>
            </header>
            <label>
              <span>可用现金 USD</span>
              <input type="number" min="0" step="0.01" value={cashDraft.value} onChange={(event) => setCashDraft((current) => current ? { ...current, value: event.target.value } : current)} />
            </label>
            <div className="button-row">
              <button type="button" onClick={() => setCashDraft(null)}>取消</button>
              <button type="submit" className="primary">保存并刷新</button>
            </div>
          </form>
        </div>
      )}
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
  deleteManualExecution,
  importUsmartScreenshot,
  importZaScreenshot
}: {
  events: DisciplineEvent[];
  orders: Order[];
  holdings: Holding[];
  selectedTicker: string;
  recordZaManualExecution: () => Promise<void>;
  submitOfflineTrade: (form: OfflineTradeForm) => Promise<void>;
  deleteManualExecution: (order: Order) => Promise<void>;
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
              {order.order_type === "MANUAL" && <button type="button" onClick={() => deleteManualExecution(order)}>删除</button>}
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
