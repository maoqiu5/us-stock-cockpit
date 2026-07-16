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
  Play,
  Radar,
  ShieldCheck,
  SlidersHorizontal,
  WalletCards
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const USMART_SCREENSHOT_PATH =
  "/Users/brian/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_5oxgvzo5wkcv21_448a/temp/RWTemp/2026-07/b3cb3351d259bd6f77573a1d380b26e0.jpg";
const ZA_SCREENSHOT_PATH =
  "/Users/brian/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_5oxgvzo5wkcv21_448a/temp/RWTemp/2026-07/4ce6a65a5e65b7986b40f0da36549bc8.jpg";

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

type HoldingAdvice = {
  ticker: string;
  broker: string;
  action: string;
  confidence: number;
  reason: string;
  risk_level: "low" | "medium" | "high";
  suggested_weight: number;
};

type CandidateStock = {
  ticker: string;
  name: string;
  sector: string;
  score: number;
  reason: string;
  action: string;
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
  best_ticker: string;
  average_annual_return: number;
  average_max_drawdown: number;
  tuning_note: string;
};

type ValidateTickerResult = {
  ticker: string;
  valid: boolean;
  name: string;
  price: number;
  source: string;
  reason: string;
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
  holdingAdvice: HoldingAdvice[];
  candidates: CandidateStock[];
  allocation: PortfolioOptimization | null;
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
    refreshLabel: isOpen ? "10秒自动刷新" : "开盘后10秒刷新"
  };
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store"
  });
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
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
    holdingAdvice: [],
    candidates: [],
    allocation: null
  });
  const [newTicker, setNewTicker] = useState("");
  const [tickerValidation, setTickerValidation] = useState<ValidateTickerResult | null>(null);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [validation, setValidation] = useState<ModelValidationItem[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("pe_v1");
  const [selectedTicker, setSelectedTicker] = useState("NOK.US");
  const [analysisType, setAnalysisType] = useState("offline");
  const [preparedOrder, setPreparedOrder] = useState<PreparedOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [marketSession, setMarketSession] = useState(() => getUSMarketSession());
  const loadingRef = useRef(false);

  const load = useCallback(async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const [summary, strategies, watchlist, events, orders, risk, brokers, execution, quotes, sources, holdings, holdingAdvice, candidates, allocation] = await Promise.all([
        fetchJson<DashboardSummary>("/dashboard/summary"),
        fetchJson<StrategyModel[]>("/strategies"),
        fetchJson<WatchlistItem[]>("/watchlist"),
        fetchJson<DisciplineEvent[]>("/discipline/events"),
        fetchJson<Order[]>("/orders"),
        fetchJson<RiskStatus>("/risk/status"),
        fetchJson<BrokerCapability[]>("/brokers/capabilities"),
        fetchJson<ExecutionConfig>("/execution/config"),
        fetchJson<MarketQuote[]>("/market/quotes"),
        fetchJson<DataSourceStatus[]>("/data-sources/status"),
        fetchJson<Holding[]>("/portfolio/holdings"),
        fetchJson<HoldingAdvice[]>("/advice/holdings"),
        fetchJson<CandidateStock[]>("/screening/candidates"),
        fetchJson<PortfolioOptimization>("/portfolio/optimization")
      ]);
      setData({ summary, strategies, watchlist, events, orders, risk, brokers, execution, quotes, sources, holdings, holdingAdvice, candidates, allocation });
      setLoading(false);
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    load().catch(() => {
      setLoading(false);
      setNotice("后端暂未连接，正在显示前端骨架。");
    });
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => setMarketSession(getUSMarketSession()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!marketSession.isOpen) return undefined;
    load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    const timer = window.setInterval(() => {
      load().catch(() => setNotice("自动刷新失败，正在保留最近一次数据。"));
    }, 10_000);
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
    await fetchJson<Order>("/manual-executions", {
      method: "POST",
      body: JSON.stringify({
        broker: "za-bank",
        ticker: selectedTicker,
        side: "BUY",
        qty: 1,
        price: defaultPriceForTicker(selectedTicker),
        executed_at: "07/16 14:04",
        note: "ZA Bank App 手工确认"
      })
    });
    await load();
    setNotice("已记录一笔 ZA Bank 手工成交。");
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
    const validation = tickerValidation?.ticker === normalized ? tickerValidation : await validateTicker(normalized);
    if (!validation.valid) {
      setNotice(validation.reason);
      return;
    }
    await fetchJson<WatchlistItem>("/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker: normalized, name: validation.name })
    });
    setNewTicker("");
    setTickerValidation(null);
    await load();
    setNotice(`${normalized} 已加入股票池，系统会纳入行情、候选跟踪和模型评测。`);
  }

  async function validateTicker(ticker = newTicker) {
    const normalized = ticker.trim().toUpperCase();
    const result = await fetchJson<ValidateTickerResult>(`/watchlist/validate?ticker=${encodeURIComponent(normalized)}`);
    setTickerValidation(result);
    setNotice(result.reason);
    return result;
  }

  async function deleteWatchlistTicker(ticker: string) {
    await fetchJson(`/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });
    await load();
    setNotice(`${ticker} 已从股票池删除。`);
  }

  async function validateModels() {
    const result = await fetchJson<ModelValidationItem[]>("/models/validation");
    setValidation(result);
    setNotice(`已验证 ${result.length} 个策略模型，结果已更新到股票池页。`);
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span>美股驾驶舱</span>
          <small>US STOCK COCKPIT</small>
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
            <button className="sync">登录同步</button>
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
            holdingAdvice={data.holdingAdvice}
            candidates={data.candidates}
            allocation={data.allocation}
            validation={validation}
            newTicker={newTicker}
            tickerValidation={tickerValidation}
            setNewTicker={setNewTicker}
            setTickerValidation={setTickerValidation}
            validateTicker={validateTicker}
            addStockToWatchlist={addStockToWatchlist}
            deleteWatchlistTicker={deleteWatchlistTicker}
            load={load}
            importPreviousClose={importPreviousClose}
            validateModels={validateModels}
          />
        )}
        {active === "discipline" && (
          <Discipline
            events={data.events}
            orders={data.orders}
            holdings={data.holdings}
            recordZaManualExecution={recordZaManualExecution}
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
  holdingAdvice,
  candidates,
  allocation,
  validation,
  newTicker,
  tickerValidation,
  setNewTicker,
  setTickerValidation,
  validateTicker,
  addStockToWatchlist,
  deleteWatchlistTicker,
  load,
  importPreviousClose,
  validateModels
}: {
  items: WatchlistItem[];
  quotes: MarketQuote[];
  holdings: Holding[];
  holdingAdvice: HoldingAdvice[];
  candidates: CandidateStock[];
  allocation: PortfolioOptimization | null;
  validation: ModelValidationItem[];
  newTicker: string;
  tickerValidation: ValidateTickerResult | null;
  setNewTicker: (value: string) => void;
  setTickerValidation: (value: ValidateTickerResult | null) => void;
  validateTicker: (ticker?: string) => Promise<ValidateTickerResult>;
  addStockToWatchlist: (ticker: string) => Promise<void>;
  deleteWatchlistTicker: (ticker: string) => Promise<void>;
  load: () => Promise<void>;
  importPreviousClose: () => Promise<PreviousCloseImportResult>;
  validateModels: () => Promise<void>;
}) {
  const quoteMap = new Map(quotes.map((quote) => [quote.ticker, quote]));
  const holdingTickers = new Set(holdings.map((holding) => holding.ticker));
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
            <button onClick={validateModels}>验证模型</button>
          </div>
        </div>
        <div className="add-stock-row">
          <label>新增监控股票
            <input
              value={newTicker}
              onChange={(event) => {
                setNewTicker(event.target.value.toUpperCase());
                setTickerValidation(null);
              }}
              placeholder="例如 MSFT / GOOGL / QQQ"
            />
          </label>
          <button onClick={() => validateTicker(newTicker)}>校验代码</button>
          <button className="primary" disabled={!tickerValidation?.valid || tickerValidation.ticker !== newTicker.trim().toUpperCase()} onClick={() => addStockToWatchlist(newTicker)}>加入股票池</button>
        </div>
        {tickerValidation && (
          <div className={`validation-box ${tickerValidation.valid ? "valid" : "invalid"}`}>
            <strong>{tickerValidation.ticker || "未输入"}</strong>
            <span>{tickerValidation.reason}</span>
            {tickerValidation.valid && <em>{tickerValidation.name} · {fmtMoney(tickerValidation.price)} · {tickerValidation.source}</em>}
          </div>
        )}
        <table>
          <thead>
            <tr><th>股票</th><th>现价</th><th>涨跌</th><th>PE</th><th>PEG</th><th>ROI</th><th>增长</th><th>趋势</th><th>资格</th><th>信号</th><th>操作</th></tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const quote = quoteMap.get(item.ticker);
              return (
                <tr key={item.ticker}>
                  <td><b>{item.ticker}</b><span>{item.name}</span></td>
                  <td>{quote ? fmtMoney(quote.price) : "-"}</td>
                  <td className={quote && quote.pct_change < 0 ? "negative" : "positive"}>{quote ? pct(quote.pct_change) : "-"}</td>
                  <td>{item.pe}</td>
                  <td>{item.peg}</td>
                  <td>{pct(item.roi)}</td>
                  <td>{pct(item.growth)}</td>
                  <td>{item.trend}</td>
                  <td>{item.eligible ? "可交易" : "观察"}</td>
                  <td><em>{item.signal}</em></td>
                  <td>
                    {holdingTickers.has(item.ticker) ? (
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
            <h2>持仓实时交易建议</h2>
            <p>根据持仓盈亏、仓位集中度和风控纪律生成，只用于决策提示。</p>
          </div>
          <span className="badge">{holdingAdvice.length} 条</span>
        </div>
        <div className="advice-grid">
          {holdingAdvice.map((item) => (
            <article key={`${item.broker}-${item.ticker}`} className={`advice-card ${item.risk_level}`}>
              <strong>{item.ticker}</strong>
              <b>{item.action}</b>
              <span>建议权重 {item.suggested_weight.toFixed(2)}% · 置信 {Math.round(item.confidence * 100)}%</span>
              <p>{item.reason}</p>
            </article>
          ))}
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
              <span>{candidate.sector} · {candidate.action}</span>
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
            <p>点击“验证模型”后，用当前股票池批量回测三套策略，并给出参数调教方向。</p>
          </div>
          <span className="badge">{validation.length ? `${validation.length} 个模型` : "等待验证"}</span>
        </div>
        <div className="advice-grid">
          {validation.map((item) => (
            <article key={item.strategy_id} className="advice-card">
              <strong>{item.strategy_id}</strong>
              <b>{pct(item.average_annual_return)}</b>
              <span>最佳 {item.best_ticker} · 平均回撤 {pct(item.average_max_drawdown)} · 样本 {item.tested}</span>
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

function Discipline({
  events,
  orders,
  holdings,
  recordZaManualExecution,
  importUsmartScreenshot,
  importZaScreenshot
}: {
  events: DisciplineEvent[];
  orders: Order[];
  holdings: Holding[];
  recordZaManualExecution: () => Promise<void>;
  importUsmartScreenshot: () => Promise<void>;
  importZaScreenshot: () => Promise<void>;
}) {
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
            <p>ZA Bank 暂按手工确认，执行后在这里补记，后续可做对账。</p>
          </div>
          <button onClick={recordZaManualExecution}>记录 ZA 成交</button>
        </div>
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
