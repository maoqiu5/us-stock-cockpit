# 美股驾驶舱项目交接说明

这份文档面向“接手本项目的另一个 AI 或开发者”。目标是让对方能理解当前项目的产品意图、代码结构、数据来源、策略逻辑、本地存储规则，并能在同一个工作区复刻运行。

## 1. 项目定位

本项目是一个本地运行的美股投资驾驶舱，不是公开网站，也不是自动无脑下单系统。它的核心任务是：

- 读取真实行情、基本面、历史价格和第三方候选股参考。
- 把每日获取到的股票数据写入本地工作区，形成后续缓存和分析依据。
- 根据实时行情、持仓状态、策略模型和回测质量生成股票池、候选股、执行计划。
- 只使用真实数据做分析和回测；数据缺失时宁愿为空、跳过或返回错误，不使用模拟数据补齐。
- 支持人工或券商 API 前的交易纪律校验，避免绕过风控。

用户偏好是“实用驾驶舱”，不是营销落地页。界面应紧凑、可扫描、便于每天重复查看，不要使用过多解释性文案。

## 2. 技术栈

前端：

- Next.js 15
- React 19
- TypeScript
- lucide-react 图标
- 主要文件：`app/page.tsx`、`app/globals.css`

后端：

- FastAPI
- Pydantic
- Python 标准库 `urllib` 获取公开行情
- 主要文件：`backend/app/main.py`

本地数据：

- 手工状态：`data/usstock/local_state.json`
- 行情缓存：`data/usstock/market_cache/quotes/YYYY-MM-DD.json`
- 历史收盘缓存：`data/usstock/market_cache/daily_closes/TICKER.json`
- 候选股抓取缓存：`data/usstock/market_cache/screening/*.json`

## 3. 目录结构

```text
.
├── app/
│   ├── page.tsx              # 前端主驾驶舱，包含股票池、模型、回测、执行计划等 UI
│   ├── globals.css           # 全局样式和响应式布局
│   └── layout.tsx
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 路由、状态加载保存、组合业务逻辑
│   │   ├── models.py         # API 输入输出模型
│   │   ├── data_sources.py   # 行情、基本面、股票池动态计算
│   │   ├── historical_prices.py # Yahoo 历史价格、开盘判断、历史缓存
│   │   ├── market_cache.py   # 本地行情/历史/筛选缓存写入和读取
│   │   ├── strategy.py       # 因子评分、信号、回测
│   │   ├── risk.py           # 风控
│   │   ├── broker.py         # 券商适配层
│   │   ├── gold_monitor.py   # 黄金监控
│   │   ├── usmart_importer.py
│   │   └── za_importer.py
│   └── tests/
├── data/
│   ├── local_state.json
│   └── market_cache/
├── README.md
├── package.json
└── backend/requirements.txt
```

## 4. 启动方式

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
FMP_API_KEY="你的 Financial Modeling Prep key" uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
npm install
npm run dev
```

默认地址：

- 前端：`http://localhost:3000`
- 后端文档：`http://127.0.0.1:8000/docs`

注意：不要把真实 API key 写入代码、README 或提交记录。只通过环境变量传入。

## 5. 数据原则

这是项目最重要的约束：

1. 股票池、候选股、回测、模型验证必须尽量使用真实市场数据。
2. 数据获取后要写入本地工作区，供之后缓存、复盘和减少重复请求使用。
3. 不允许为了让界面“看起来完整”而制造模拟回测结果。
4. 历史数据缺失时：
   - 直接回测接口应该报错或无结果。
   - 模型验证应该把样本记为缺失。
   - UI 可以显示数据质量不足，而不是假装有结论。
5. 候选股必须是真实搜寻结果，当前规则要求股价低于 10 美元，并可参考第三方荐股/筛选平台。

## 6. 当前数据源

行情：

- 优先 FMP quote API，环境变量为 `FMP_API_KEY`。
- Yahoo chart API 用于盘中、昨收和历史日线。
- AkShare 若本地可用，可作为补充路径。
- 若在线行情失败，会尽量读取本地缓存；用于分析时应标明来源。

基本面：

- FMP profile、key metrics、financial ratios 等端点。
- 基本面指标会按实时股价重新估算 PE、PEG、ROI 等动态展示值。

候选股：

- FMP company screener。
- FMP v3 stock-screener。
- FMP stock-list。
- Finviz 低价股 screener 作为第三方参考和 fallback。

历史价格：

- Yahoo daily chart。
- 成功获取后写入 `data/usstock/market_cache/daily_closes/`。
- `strategy.run_backtest()` 只使用历史真实收盘序列。

本地缓存模块：

- `backend/app/market_cache.py`
- `save_quotes()` 写入当天 quote JSON。
- `latest_cached_quotes()` 从最近缓存补报价。
- `save_daily_closes()` 合并写入单票历史收盘。
- `cached_daily_closes()` 读取指定日期范围。
- `save_screening_payload()` 保存候选股原始/最终结果。

## 7. 本地持久化

`backend/app/main.py` 启动时调用 `_load_local_state()`，把 `data/usstock/local_state.json` 中的状态恢复到内存。状态变更后调用 `_save_local_state()` 写回。

当前本地状态包括：

- 股票池自定义条目。
- 黄金手工购买记录。
- 持仓导入记录。
- 手工成交记录。
- 自动化暂停状态。

黄金购买记录相关接口：

- `GET /gold/manual-trades`
- `POST /gold/manual-trades`
- `DELETE /gold/manual-trades/{trade_id}`

如果用户说“我录入过黄金购买记录但没有了”，先检查：

1. `data/usstock/local_state.json` 是否存在 `gold_manual_trades`。
2. 后端是否从同一个工作区启动。
3. 前端请求的后端是否是 `127.0.0.1:8000` 这个实例。
4. 是否误删或没有触发 `_save_local_state()`。

## 8. 股票池逻辑

股票池入口：

- `GET /watchlist`
- `POST /watchlist`
- `DELETE /watchlist/{ticker}`
- `GET /watchlist/validate?ticker=...`

动态计算位于 `backend/app/data_sources.py`：

- `market_quotes()` 获取或补齐行情。
- `dynamic_watchlist()` 把基础股票池、实时报价、基本面、持仓、模型验证结果合并。
- `_dynamic_watchlist_item()` 重算单只股票的 PE、PEG、ROI、trend、signal、model_score。

趋势判断：

- 主要根据当前涨跌幅 `pct_change`：
  - 明显上涨为“上行”。
  - 小幅波动为“横盘”。
  - 明显下跌为“下行”。
- 趋势不是主观文本，而是行情变化的分类标签。

信号判断：

- 因子评分来自 `strategy.score_watchlist_item()`。
- 检查项包括 PE、PEG、ROI、growth、trend。
- 估值过热时倾向卖出或减仓。
- 因子和模型验证通过时倾向加入监控或买入。
- 如果用户已有持仓，还会加入持仓盈亏、当前仓位权重、目标仓位等上下文。

## 9. 三套策略模型

策略定义主要在 `backend/app/strategy.py`，模型验证在 `backend/app/main.py` 的 `/models/validation`。

当前三套模型：

1. `pe_v1`
   - 含义：估值纪律模型。
   - 重点：PE 是否过高、回撤时降低暴露。
   - 适合：避免高估值和大回撤阶段的风险扩张。

2. `peg_v1`
   - 含义：成长估值平衡模型。
   - 重点：PEG 和短期动量。
   - 适合：希望在增长和价格趋势之间找平衡的标的。

3. `roi_v1`
   - 含义：质量/资本回报模型。
   - 重点：ROI，且遇到单日大跌时降低风险暴露。
   - 适合：偏质量和盈利能力的标的。

每个股票都会尽量跑三套模型，但前提是有足够真实历史数据。没有数据的股票不会用模拟结果填充。

## 10. 回测和模型验证

单次回测：

- 接口：`POST /strategies/{strategy_id}/backtest`
- 输入：ticker、start_date、end_date、mode
- 输出：年化收益、PnL、胜率、盈亏比、最大回撤、交易次数、相对 SPY 的基准收益、曲线采样点。

回测意义：

- 用历史真实价格检查策略在过去会如何表现。
- 帮用户识别“看起来有逻辑但历史表现很差”的规则。
- 不是未来收益保证，只是纪律和风险校验工具。

最大回撤含义：

- 从历史净值高点跌到之后低点的最大跌幅。
- 例如最大回撤 `-20%` 表示策略曾从阶段高点跌掉 20%。
- 同等收益下，回撤越小通常更容易执行。

模型验证周期：

- 短周期：`2026-05-01` 到 `2026-07-16`，权重 30%。
- 中周期：`2025-07-16` 到 `2026-07-16`，权重 50%。
- 长周期：`2023-07-16` 到 `2026-07-16`，权重 20%。

验证时会记录：

- `valid_samples`
- `missing_samples`
- `data_quality`
- `data_quality_label`
- 各周期收益和回撤

回测周期不是越长越好：

- 长周期能看到更多市场环境，但可能包含过时结构。
- 短周期更贴近当前市场，但容易被短期行情误导。
- 当前采用三周期加权，是为了同时看近期、中期和长期稳定性。

## 11. 执行计划

接口：`GET /execution/plan`

执行计划不是直接下单，它是“按照策略执行”的落地层。它会综合：

- 当前股票池信号。
- 三套模型验证分数。
- 当前持仓数量和成本。
- 当前市值、账户总额和权重。
- 目标仓位。
- 风控阻断条件。

输出字段包括：

- `side`：BUY / SELL / NONE
- `current_weight`
- `target_weight`
- `delta_amount`
- `suggested_qty`
- `stop_loss_price`
- `take_profit_price`
- `confidence`
- `blockers`

前端中“持仓实时交易建议”面板已删除，但后端 `/advice/holdings` 仍保留。如果未来要恢复旧 UI，可以重新调用该接口；如果继续走更完整的策略执行路径，应优先使用 `/execution/plan`。

## 12. 候选股发现

接口：`GET /screening/candidates`

当前要求：

- 真实搜寻，不写死固定股票。
- 只纳入 10 美元以下股票。
- 可从第三方荐股/筛选平台作为参考。
- 候选股也要进入动态股票池计算和模型验证。

候选股流程：

1. `_low_price_candidate_universe()` 获取低价股原始池。
2. 依次尝试 FMP screener、FMP v3 screener、FMP stock-list。
3. 如果 FMP 不可用或不足，尝试 Finviz 低价股 screener。
4. 原始抓取结果保存到 `data/usstock/market_cache/screening/`。
5. 转为 `WatchlistItem` 后调用 `dynamic_watchlist()`。
6. 用 `_candidate_model_summary()` 计算模型验证摘要。
7. 生成 `CandidateStock`，包含 price、score、model_score、data_quality、signal、reference_source。

候选股接口可能较慢，因为它会对真实候选逐个获取行情、基本面和历史数据。后续可以按“ticker + 日期”缓存模型摘要。

## 13. 风控和交易

风控在 `backend/app/risk.py`，券商适配在 `backend/app/broker.py`。

当前项目支持：

- Paper broker。
- uSMART 请求预演。
- IBKR 备用路径。
- ZA Bank 手工执行记录。

重要原则：

- 默认不自动实盘下单。
- live 模式必须显式设置 `ENABLE_LIVE_TRADING=true`。
- 所有订单在提交前必须经过风控。
- ZA Bank 当前按手工路径处理，不做 App 自动点击或非公开接口。

相关接口：

- `GET /risk/status`
- `GET /orders`
- `POST /orders`
- `POST /orders/preview`
- `POST /manual-executions`
- `GET /execution/config`
- `GET /brokers/capabilities`

## 14. 前端交互

主要 UI 在 `app/page.tsx`。

当前前端特点：

- 左侧目录树可折叠。
- 股票池表格展示趋势、现价、涨跌、PE、PEG、ROI、模型分、信号等。
- 模型验证按钮有 loading 状态，验证后会刷新股票池模型相关数据。
- 已删除过长的趋势依据文本展示。
- 已删除旧的“持仓实时交易建议”面板，改用更系统的执行计划。
- 候选股、模型验证、回测、执行计划都通过 FastAPI 获取。

样式在 `app/globals.css`，注意保持表格列宽稳定，不要让“趋势/现价/涨跌”等字段被挤成竖排。

## 15. API 速查

基础：

- `GET /health`
- `GET /dashboard/summary`
- `GET /data-sources/status`

股票池：

- `GET /watchlist`
- `POST /watchlist`
- `DELETE /watchlist/{ticker}`
- `GET /watchlist/validate`

行情：

- `GET /market/quotes`
- `POST /market/import-previous-close`

模型和策略：

- `GET /strategies`
- `POST /strategies/{strategy_id}/backtest`
- `GET /models/validation`
- `GET /signals`

候选和组合：

- `GET /screening/candidates`
- `GET /portfolio/holdings`
- `GET /portfolio/optimization`
- `GET /execution/plan`

黄金：

- `GET /gold/monitor`
- `GET /gold/manual-trades`
- `POST /gold/manual-trades`
- `DELETE /gold/manual-trades/{trade_id}`

交易和导入：

- `GET /orders`
- `POST /orders`
- `POST /orders/preview`
- `POST /manual-executions`
- `POST /imports/broker-records`
- `POST /imports/usmart-screenshot`
- `POST /imports/za-screenshot`

## 16. 验证命令

TypeScript：

```bash
PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node_modules/.bin/tsc --noEmit
```

Python 编译检查：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache .venv/bin/python -m py_compile backend/app/models.py backend/app/market_cache.py backend/app/historical_prices.py backend/app/data_sources.py backend/app/strategy.py backend/app/main.py
```

后端测试：

```bash
.venv/bin/python -m pytest backend/tests
```

如果生成 `tsconfig.tsbuildinfo`，不要把它当成业务变更；可清理。

## 17. 复刻步骤

让另一个 AI 在新机器或新工作区复刻时，按这个顺序做：

1. 安装 Python 和 Node 依赖。
2. 设置 `FMP_API_KEY` 环境变量，不要写入文件。
3. 启动 FastAPI 后端。
4. 启动 Next.js 前端。
5. 打开 `http://localhost:3000`。
6. 调用 `GET /data-sources/status` 确认 FMP/Yahoo 等状态。
7. 调用 `GET /market/quotes`，确认 `data/usstock/market_cache/quotes/` 写入当天文件。
8. 调用 `GET /watchlist`，确认股票池按实时价格重算。
9. 调用 `GET /models/validation`，确认真实历史数据不足的样本被标为缺失，而不是模拟补齐。
10. 调用 `GET /screening/candidates`，确认候选股小于 10 美元且写入 `data/usstock/market_cache/screening/`。

## 18. 已知限制和后续优化

已知限制：

- FMP 免费/低阶套餐可能有额度、延迟或端点限制。
- Yahoo 和 Finviz 都不是正式付费行情源，返回格式可能变化。
- 候选股接口会较慢，因为它现在强调真实搜寻和真实验证。
- 美股节假日/半日交易目前只做了普通工作日 9:30-16:00 ET 判断。
- 基本面实时性取决于 FMP 返回的数据，PE/PEG/ROI 是基于最新价格重新估算，不等于交易所官方实时披露值。

建议优化：

- 给候选股模型验证增加按日缓存，避免每次重复跑历史回测。
- 增加“数据质量面板”，明确展示每只股票当前 quote、fundamental、history 的来源和更新时间。
- 加入美股交易日历，替代简单工作日判断。
- 增加缓存清理和导出工具。
- 对每个候选股保留每日快照，形成可回溯的本地研究库。
- 若用户未来购买正式行情服务，可以把 `data_sources.py` 中的 quote provider 抽象为可切换 provider。

## 19. 接手注意事项

- 不要删除用户的 `data/usstock/local_state.json` 和 `data/usstock/market_cache/`，这些是本地资产。
- 不要把 API key、券商 token、私钥路径提交到项目文件。
- 不要恢复模拟回测结果。
- 不要把候选股退回硬编码列表。
- 修改 UI 时保持驾驶舱优先：密度、稳定列宽、可扫描、少解释文字。
- 修改交易路径时保持风控优先：所有真实下单必须显式开启 live 并经过风控。
