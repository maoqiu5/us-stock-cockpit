# 美股驾驶舱 CHANGELOG

本文记录项目功能、算法、部署和数据规则的详细迭代历史。之后每次更新功能、算法、数据源、部署方式或重要文档时，都在这里追加一条版本记录；`docs/PRD.md` 只保留简短版本摘要和产品原则。

格式：

```text
## YYYY-MM-DD - 版本标题

- 类型：
- 背景：
- 变更：
- 验证：
- 上线：
- 后续：
```

## 2026-07-23 - 股票池提交反馈与配舱前置

- 类型：前端 / 体验 / 文档
- 背景：用户要求所有提交动作都有明确弹窗反馈；股票池追踪列表过宽，需要隐藏不重要列；持仓配舱策略需要提前展示，不再每次拉到页面底部查看。
- 变更：
  - 前端新增统一提交反馈浮层，线下交易、现金设置、股票池新增/删除、模型验证、快照生成、昨收导入、截图导入、自动执行状态切换等提交动作会显示成功或失败提示。
  - 股票池线下交易和现金设置弹窗在提交失败时不自动关闭，便于直接修正后再次提交。
  - 股票池页面把“今日配舱”和“账户余额与仓位优化”提前到监控表格上方，打开股票池后先看账户弹药、现金垫、可动用资金、混合加仓和减仓顺序。
  - 股票池追踪表从 18 列压缩为 12 列，移除 PE、PEG、ROI、模型分、信号、信号依据等独立列；关键信号、模型分和依据合并进“中长线策略”列。
  - 调整表格最小宽度和换行规则，降低横向滚动压力。
- 验证：本地 `tsc --noEmit` 通过；线上 `https://brianhub.net/usstock` 返回 `200`，`/usstock/api/health` 返回 `200`，`/usstock/api/watchlist` 返回 `200`，`/usstock/api/execution/plan` 返回 `200`。
- 上线：已直接同步 VPS 并重建 frontend；Compose 顺带使用缓存重建/重启 backend，但未修改后端代码；未通过 GitHub。
- 后续：可继续增加“展开详情”行，把 PE/PEG/ROI/完整信号依据放到单票详情里，而不是回到超宽表格。

## 2026-07-23 - 合并今日配舱与仓位优化模块

- 类型：前端 / 体验 / 文档
- 背景：用户指出“今日配舱”和“账户余额与仓位优化”展示内容重复，影响股票池页面的决策效率。
- 变更：
  - 股票池页面删除独立的“账户余额与仓位优化”大模块。
  - 将账户总额、当前现金、目标现金和前几条仓位优化建议合并到“今日配舱策略”底部，作为仓位优化依据。
  - “今日配舱策略”统一承载现金垫、可动用资金、混合加仓、减仓顺序和中长线目标仓位信息。
- 验证：本地 `tsc --noEmit` 通过；线上 `https://brianhub.net/usstock` 返回 `200`，`/usstock/api/health` 返回 `200`，`/usstock/api/watchlist` 返回 `200`，`/usstock/api/execution/plan` 返回 `200`。
- 上线：已直接同步 VPS 并重建 frontend；Compose 顺带使用缓存重建/重启 backend，但未修改后端代码；未通过 GitHub。
- 后续：如信息仍偏多，可继续把仓位优化建议折叠为“展开依据”。

## 2026-07-23 - 候选股发现改为中长期荐股逻辑

- 类型：算法 / 后端 / 前端 / 文档
- 背景：用户指出如果配舱策略是中长期，而候选股发现仍偏短线热度或异动，系统入口和执行会断层。
- 变更：
  - 候选股评分新增中长期质量分，综合 ROI、成长、PEG、PE 和趋势状态。
  - 候选股动作从“加入监控/观察等待/暂不加入”改为中长期口径：`中长期候选`、`观察候选`、`估值偏贵，等回调`、`趋势破坏，暂避`、`暂不纳入`。
  - 估值过热、PEG/PE 偏贵或趋势过热的标的，即使模型分较高，也不直接作为立即加入型候选，而是等待回调。
  - 趋势下行或风险信号标的直接归为暂避。
  - 候选股理由改为“中长期真实筛选”，显示质量分、估值/成长因子分、多周期模型分、真实数据质量、趋势、流动性和第三方参考。
  - 旧口径候选股缓存（例如“加入监控/观察等待/全价位真实筛选”）不再直接返回，避免上线后继续显示短线入口文案。
  - 前端候选股模块标题改为“中长期候选股发现”，说明先看质量、估值、趋势和真实数据质量。
  - 新增回归测试覆盖估值过热等回调、优质标的进入中长期候选、旧候选股缓存失效。
- 验证：候选股相关 5 个后端测试已在 VPS backend 容器通过；本地 TypeScript 检查通过；线上 `/usstock` 返回 `200`，`/usstock/api/health` 返回 `200`，`/usstock/api/screening/candidates` 返回新动作口径和“中长期真实筛选”理由。
- 上线：已直接同步 VPS 并重建 backend/frontend；未通过 GitHub。
- 后续：可继续接入更完整的基本面字段，例如自由现金流、负债率、营收增速、毛利率、ROE 和行业相对估值。

## 2026-07-23 - 股票池中长线策略与内嵌交易记录

- 类型：功能 / 算法 / 前端 / 后端 / 风控
- 背景：用户要求股票池持仓策略面向中长线投资，给出合理买入点和卖出点，而不是短线量化交易；同时要求在股票池内直接录入线下买入/卖出，不再切换到持仓纪律模块；ZA Bank 也需要能手动设置现金并参与账户级建议。
- 变更：
  - 新增 `POST /portfolio/account-balances/{broker}`，支持手动设置 ZA Bank、uSMART 等账户可用现金，并写入本地/服务器状态。
  - 账户余额接口默认显示 ZA Bank 和 uSMART，即使现金暂未设置，也能在股票池页面手动录入弹药。
  - `/execution/plan` 对未持仓 BUY 标的不再只给现金最多账户生成计划，而是对所有有现金/资产的账户生成账户级建议。
  - 执行计划理由改为中长线语气：股票池信号、模型分、分批建仓、目标仓位、等待合理买入区间。
  - 股票池账户卡新增“调整现金”入口。
  - 股票池每只股票新增“记录交易”按钮，点击后在当前页面弹出线下交易录入框，提交后调用已有线下交易接口并刷新数据。
  - 新增回归测试覆盖手动设置 ZA Bank 现金、核心账户默认可见、未持仓 BUY 标的按多个现金账户生成计划。
- 验证：本地 TypeScript 检查通过；VPS backend 容器内 `python -m pytest /app/backend/tests/test_strategy_and_risk.py -q` 通过，32 个测试全部通过；frontend 生产构建通过。
- 上线：已直接同步 VPS 并重建 backend/frontend 容器；线上 `/usstock`、`/usstock/api/health`、`/usstock/api/execution/plan`、`/usstock/api/portfolio/account-balances` 均返回 `200`；执行计划确认包含 ZA Bank；未通过 GitHub。
- 后续：继续把买入/卖出价位算法从简单目标仓位升级为更完整的中长线估值区间、回撤买点、目标收益区、基本面恶化退出线。

## 2026-07-22 - 候选股取消 10 美元以下限制

- 类型：功能 / 算法 / 数据源 / 文档
- 背景：用户要求股票池候选股不再只筛选 10 美元以下股票，避免错过中高价位但质量更好的美股标的。
- 变更：
  - FMP `company-screener` 和 v3 `stock-screener` 请求移除 `priceLowerThan=10`，改为全价位真实扫描。
  - Finviz fallback 移除 `sh_price_u10` 过滤。
  - 本地候选股过滤取消 10 美元上限，仅保留最低价格、成交量、成交额、市值、交易所和普通股类型约束。
  - 候选股缓存 key 从 `low_price_candidates` 切换为 `stock_candidates`，避免上线后继续读取旧低价股缓存。
  - 候选股理由文案从“10美元以下真实筛选”改为“全价位真实筛选”。
  - PRD 更新候选股规则；测试改为验证 10 美元以上股票可通过质量过滤。
- 验证：本地 TypeScript 检查通过；后端编译通过；`./.venv/bin/python -m pytest backend/tests/test_strategy_and_risk.py` 通过，29 个测试全部通过。
- 上线：已直接同步 VPS 并重建 backend 容器；frontend 未改代码，沿用上一个正常镜像；线上 `/usstock`、`/usstock/api/health`、`/usstock/api/screening/candidates` 均返回 `200`，候选股已出现 10 美元以上标的；未通过 GitHub。
- 后续：可继续增加价格区间/行业/市值筛选器，让用户手动切换候选股发现偏好。

## 2026-07-22 - 股票池持仓与执行计划按账户拆分

- 类型：功能 / 算法 / 前端 / 后端 / 风控
- 背景：用户指出 ZA Bank 和 uSMART 两个账户可能同时买入同一只股票，如果股票池把同 ticker 持仓合并，会导致成本、盈亏、仓位建议和模型执行判断混乱。
- 变更：
  - `/execution/plan` 从按 ticker 汇总持仓改为按账户生成执行计划；同一股票跨账户持有时，分别返回 ZA Bank / uSMART 的账户现金、账户净值、当前仓位、目标仓位、建议股数和纪律价。
  - `/portfolio/optimization` 的当前/目标仓位按对应账户净资产计算，保留全账户现金垫作为总体风险提示。
  - 股票池表格的持仓、成本、持仓盈亏、仓位列改为分账户显示。
  - 执行策略、今日配舱、减仓顺序和仓位优化列表显示账户名，避免用户不知道该在哪个券商 App 执行。
  - 新增回归测试，覆盖同一 ticker 在两个账户中持有时必须生成两条账户级执行计划。
- 验证：本地 TypeScript 检查通过；后端编译通过；`./.venv/bin/python -m pytest backend/tests/test_strategy_and_risk.py` 通过，29 个测试全部通过。
- 上线：已直接同步到 VPS，并重建 backend/frontend 容器；线上 `/usstock`、`/usstock/api/health`、`/usstock/api/execution/plan`、`/usstock/api/portfolio/optimization` 均返回 `200`；未通过 GitHub。
- 后续：可继续加入账户级目标现金垫设置，例如不同账户保留不同现金比例。

## 2026-07-22 - 持仓纪律线下交易支持撤回删除

- 类型：功能 / 风控 / 前端 / 后端
- 背景：用户要求持仓纪律里的线下交易可以撤回或删除，避免录错成交后只能手工改数据。
- 变更：新增 `DELETE /manual-executions/{order_id}`，仅允许删除 `MANUAL` 线下交易记录；删除时同步移除对应纪律事件，并按原交易方向反向回滚本地现金和持仓。
- 前端：持仓纪律的执行记录列表中，手工线下交易显示“删除”按钮，点击前弹窗确认，删除后刷新持仓、订单和纪律事件。
- 验证：本地 TypeScript 检查通过；后端编译通过；`./.venv/bin/python -m pytest backend/tests/test_strategy_and_risk.py` 通过，28 个测试全部通过。
- 上线：已直接同步 `backend/app/main.py`、`app/page.tsx`、测试和文档到 VPS，并重建 backend/frontend 容器；线上 `/usstock` 返回 `200`，`/usstock/api/health` 返回 `200`；未通过 GitHub。
- 后续：如后续需要更严格审计，可改成“撤销标记 + 保留原始记录”，而不是物理删除记录。

## 2026-07-22 - 股票池监控列表持仓置顶

- 类型：前端 / 体验
- 背景：用户要求股票池监控列表中已持仓股票优先显示，方便先看当前风险、盈亏和持仓纪律。
- 变更：股票池表格渲染前按持仓状态排序；已持仓标的显示在最上面，持仓内部按持仓市值从高到低排列，未持仓标的保持原股票池顺序。
- 验证：本地 TypeScript 检查通过；线上 `https://brianhub.net/usstock` 返回 `200`；线上 `/usstock/api/health` 返回 `200`；VPS `app/page.tsx` 已确认包含 `sortedWatchlistItems` 持仓置顶排序逻辑。
- 上线：已直接同步 `app/page.tsx`、`CHANGELOG.md`、`docs/PRD.md` 到 VPS，并重建 `frontend` 容器；Compose 同步重启了 backend/frontend，健康检查正常；未通过 GitHub。
- 后续：如需要，可再增加“持仓优先/信号优先/模型分优先”的排序切换。

## 2026-07-21 - P1-P4 股票池操盘路线图迭代

- 类型：功能 / 算法 / 数据资产 / 前端 / 测试
- 背景：用户要求按路线图继续完成 P1-P4 迭代，让美股股票池更接近盘中操盘台，并直接上线到 VPS，不通过 GitHub。
- 变更：
  - P1：股票池接入本地真实日线缓存计算 MA5、MA20、20 日高低位距离和 ATR 代理指标；缺少真实缓存时保持空值，不生成模拟指标。
  - P1：盯盘评分加入均线结构、20 日高低位位置和数据状态约束，缓存/昨收行情只允许观察。
  - P2：模型验证增加 6 小时缓存，并将最新验证结果、股票模型分和数据质量写入本地 `model_validation_latest` 数据资产。
  - P3：新增 `/daily-snapshot`，可把当日股票池、执行计划、候选股、持仓、账户余额和纪律通知写入本地快照。
  - P3：新增 `/daily-review` 和 `/data-assets/summary`，用于查看盘后复盘摘要和本地行情/日线/筛选数据资产。
  - P4：新增 `/notifications` 纪律通知，覆盖现金垫不足、候选股刷新中、风险信号和非实时行情提醒。
  - 前端股票池新增纪律通知、本地数据资产、盘后复盘三块紧凑面板，并加入“生成今日快照”按钮。
  - 前端盯盘列补充 MA5/MA20 与 ATR 信息，技术指标不足时显示日线缓存不足。
- 验证：
  - `PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit` 通过。
  - `PYTHONPYCACHEPREFIX=/tmp/usstock-pycache ./.venv/bin/python -m compileall backend/app backend/tests` 通过。
  - `./.venv/bin/python -m pytest backend/tests/test_strategy_and_risk.py` 通过，27 个测试全部通过。
- 上线：待同步到 VPS 并重建 `backend`、`frontend` 容器；不通过 GitHub。
- 后续：继续深化真实分钟 VWAP、相对成交量、新闻/财报催化、walk-forward 明细表和通知推送渠道。

## 2026-07-21 - P0 测试稳定性与候选股快返回保障

- 类型：测试 / 稳定性
- 背景：路线图 P0 要先修稳定性与数据可信度；旧测试依赖 `NOK.US`、`SMR.US` 必须存在于当前股票池，但真实股票池会随用户持仓和导入变化，不应被测试写死。
- 变更：
  - 将因子评分和估值过热信号测试改为构造独立测试标的。
  - 将行情 fallback 测试改为 monkeypatch 外部数据源，避免真实网络请求影响测试稳定性。
  - 将股票池新增/建议测试中的候选股路径改为缓存快返回测试数据，避免触发真实扫描。
  - 新增候选股缓存快返回与低价股过滤测试。
- 验证：`PYTHONPYCACHEPREFIX=/tmp/usstock-pycache ./.venv/bin/python -m compileall backend/app backend/tests` 通过；`./.venv/bin/python -m pytest backend/tests/test_strategy_and_risk.py` 通过，23 个测试耗时约 1.67 秒。
- 上线：测试与文档同步到 VPS；无运行时代码改动，不重建容器；未通过 GitHub 发布。
- 后续：继续给行情新鲜度、数据资产清单和核心接口缓存命中增加测试。

## 2026-07-21 - 拆分 PRD 与 CHANGELOG 职责

- 类型：文档 / 流程
- 背景：用户要求 `CHANGELOG.md` 记录当前所有迭代，`docs/PRD.md` 只保留简单产品说明和最近版本摘要；之后每次更新功能或算法时追加版本记录。
- 变更：
  - 新增 `CHANGELOG.md`，汇总当前所有关键迭代历史。
  - 精简 `docs/PRD.md` 的长变更记录，改为版本记录规则、最近版本摘要和后续迭代路线图。
  - 更新 `README.md`、`docs/PROJECT_HANDOFF.md`、`docs/AI_RESUME_CONTEXT.md`，统一维护规则。
  - 明确之后详细迭代写 `CHANGELOG.md`，PRD 仅在产品边界、路线图或数据原则变化时更新。
- 验证：文档检查通过；无代码改动，不需要重建容器。
- 上线：文档同步到 VPS，不重建容器。
- 后续：每次功能、算法、数据源、部署或重要文档更新，都先在 `CHANGELOG.md` 顶部追加记录。

## 2026-07-21 - 候选股快返回与低价股过滤升级

- 类型：功能 / 算法 / 性能
- 背景：候选股真实扫描依赖 FMP、Finviz、回测和第三方评级，可能拖慢股票池页面。低价股需要更严格的流动性和可交易性过滤。
- 变更：
  - `/screening/candidates` 优先返回最近一次真实缓存。
  - 缓存过期时启动后台刷新；无缓存时才同步真实扫描。
  - 低价股过滤加入价格、成交量、成交额、市值、交易所、普通股类型。
  - 候选股前端展示流动性分、成交额、市值、交易所、数据状态和来源时间。
  - 所有真实源失败时保留旧缓存或返回空，不生成模拟候选名单。
- 验证：
  - 本地 TypeScript 检查通过。
  - 后端语法编译通过。
  - 线上 `/usstock/api/health` 返回 `200`。
  - 线上 `/usstock/api/screening/candidates` 返回 `200`。
  - 旧真实缓存约 `1.7s` 返回；后台刷新后新真实扫描约 `1.0s` 返回，并包含流动性字段。
  - 线上 `/usstock` 返回 `200`。
- 上线：已直接同步代码到 VPS，并重建 `backend` 与 `frontend` 容器；未通过 GitHub 发布。
- 后续：可继续加入新闻/财报催化、盘前盘后异动、相对成交量和行业热度。

## 2026-07-21 - 股票池盯盘研判与配舱策略升级

- 类型：功能 / 算法 / 前端
- 背景：参考 A 股项目的盯盘研判与配仓策略，美股股票池需要从静态因子表升级为更接近盘中操盘的决策面板。
- 变更：
  - `/watchlist` 新增盯盘评分、盯盘研判、数据状态、行情源、更新时间。
  - 新增买入区间、追高限制、止损价、目标价、最大亏损金额。
  - `/execution/plan` 返回执行策略所需的价格纪律字段。
  - `/portfolio/optimization` 去除旧标的硬编码目标权重。
  - 仓位优化改为根据当前信号、模型分、盯盘分、持仓盈亏和仓位动态生成。
  - 前端股票池新增“数据”“盯盘”“纪律价”列。
  - 今日配舱显示买入区间、追高线和风控止损。
- 验证：
  - 本地 TypeScript 检查通过。
  - 后端语法编译通过。
  - 动态股票池计算路径可返回新字段。
  - 线上 `/usstock/api/health`、`/usstock/api/watchlist`、`/usstock/api/execution/plan`、`/usstock/api/portfolio/optimization` 和 `/usstock` 均返回 `200`。
- 上线：已直接同步代码到 VPS，并重建 `backend` 与 `frontend` 容器；未通过 GitHub 发布。
- 后续：接入 5/20 日均线、VWAP、ATR 和相对成交量，让趋势与价格纪律更稳。

## 2026-07-21 - PRD 维护规则建立

- 类型：文档 / 流程
- 背景：用户要求每次更新都要写入 PRD，避免新对话接手时缺失项目进度。
- 变更：
  - 新增 `docs/PRD.md`，记录产品定位、核心原则、功能范围、数据存储、部署规则和版本记录要求。
  - 更新 `README.md`、`docs/AI_RESUME_CONTEXT.md`、`docs/PROJECT_HANDOFF.md`，要求新会话先读 PRD 和交接文档。
  - 明确短期发布优先直接同步 VPS，不通过 GitHub，除非用户另行要求。
- 验证：文档已同步到 VPS，服务器对应路径存在。
- 上线：仅文档同步，不重建容器。
- 后续：从 2026-07-21 起，详细迭代历史迁移到 `CHANGELOG.md`，PRD 只保留简短摘要。

## 2026-07-21 - 候选股接口 Request 命名冲突修复

- 类型：修复 / 后端
- 背景：前端数据加载失败，后端候选股接口报错 `Request.__init__() got an unexpected keyword argument 'headers'`。
- 变更：
  - 将 `backend/app/main.py` 中 `urllib.request.Request` 改为别名 `UrlRequest`。
  - 避免被 `fastapi.Request` 覆盖。
  - 修复 FMP screener、FMP stock list、Finviz fallback、FMP analyst grades 等外部数据请求。
- 验证：
  - `/usstock/api/health` 返回 `200`。
  - 带访问密码请求 `/usstock/api/screening/candidates` 返回 `200`，并返回真实候选股数据。
  - 后端日志不再出现同类 `Request.__init__` 错误。
- 上线：按用户要求直接同步 `backend/app/main.py` 到 VPS，并重建 `backend` 容器；未通过 GitHub 发布。
- 后续：完整后端测试中有旧用例假设股票池必含 `NOK.US` 和 `SMR.US`，应改为状态无关测试。

## 2026-07-19 - 删除美股前台黄金盯盘

- 类型：功能调整 / 前端
- 背景：用户要求删除美股项目里的黄金盯盘。
- 变更：
  - 删除左侧导航中的“黄金盯盘”。
  - 删除前端黄金盯盘页面、走势线、线下黄金记录 UI 和相关样式。
  - 删除前端对 `/gold/monitor`、`/gold/manual-trades` 的加载。
  - README 中移除前台黄金盯盘描述。
  - 后端黄金接口和历史手工黄金记录暂时保留，避免误删历史数据。
- 验证：
  - TypeScript 检查通过。
  - 线上 `/usstock` 返回 `200`。
  - 线上 `/usstock/api/health` 返回 `200`。
  - 页面中不再出现“黄金盯盘”。
- 上线：已部署线上前端。
- 后续：如果未来彻底删除黄金后端和数据，必须先备份并经用户确认。

## 2026-07-19 - 休市黄金走势按最后报价延展

- 类型：功能 / 后端
- 背景：黄金实时走势在闭市时只有一个价格点，视觉上难看且不利于判断最后报价。
- 变更：
  - 后端黄金走势在非交易时段且真实分时点不足时，按最后真实报价生成休市走势点。
  - 曲线以最后真实报价为结尾，不改变真实报价本身。
- 验证：生产后端构建成功并启动。
- 上线：已部署线上后端。
- 后续：美股前台黄金盯盘已于后续版本移除；后端保留此逻辑仅为历史接口兼容。

## 2026-07-18 - BrianHub gateway 从 usstock 拆分

- 类型：部署架构
- 背景：`brianhub.net` 下同时运行多个项目，Caddy 不应继续由 usstock 单独拥有。
- 变更：
  - 将统一入口、TLS、Caddy 路由剥离到独立 `brianhub-gateway` 项目。
  - 美股项目只管理 `usstock_backend` 和 `usstock_frontend`。
  - Caddy/Gateway 负责 `/usstock`、`/cnstock`、`/maildesk` 等多项目路由。
  - 文档补充多项目部署边界和 Caddy 维护规则。
- 验证：生产网关和美股路径可访问。
- 上线：gateway 独立上线，usstock 后续部署不再修改 Caddy。
- 后续：新增项目、路径、TLS 或基础认证时，只改 gateway 项目。

## 2026-07-18 - 生产部署与项目隔离

- 类型：部署 / 安全 / 文档
- 背景：用户希望网页可随时随地访问，同时后续还会有其他项目部署到同一域名下。
- 变更：
  - 美股项目上线到 `https://brianhub.net/usstock`。
  - 增加 `docker-compose.prod.yml`、前后端生产 Dockerfile 和部署说明。
  - 配置 `APP_PASSWORD` 访问保护。
  - 建立生产数据路径：`/root/apps/us-stock-cockpit/data/usstock`。
  - 明确 `.env.production`、`.app_password`、`LOCAL_SECRETS.md`、`data/` 不提交。
  - 增加本地账号密码备忘文件并加入忽略。
- 验证：
  - `/usstock` 访问正常。
  - `/usstock/api/health` 返回正常。
  - 未带密码业务接口返回 `401`。
  - 带 `X-App-Password` 可访问业务接口。
- 上线：已部署到 RackNerd VPS。
- 后续：后续更新优先直接同步 VPS，除非用户要求走 GitHub。

## 2026-07-17 - 数据持久化与本地缓存

- 类型：数据 / 后端
- 背景：用户要求每天获取到的股票数据写入本地，作为后续缓存和分析依据。
- 变更：
  - 增加 SQLite 持久层。
  - 保存持仓、订单、账户余额、股票池、行情缓存、候选股 payload、纪律事件。
  - JSON 状态继续作为镜像保留。
  - 增加行情缓存、历史收盘缓存、候选股筛选缓存。
  - 明确不使用模拟数据补齐生产判断。
- 验证：本地状态可从 SQLite/JSON 恢复；行情与筛选 payload 可写入缓存。
- 上线：后续随生产部署上线。
- 后续：需要继续做数据资产清单、缓存新鲜度和数据质量评分。

## 2026-07-16 至 2026-07-17 - 股票池、持仓纪律与交易记录基础能力

- 类型：基础功能
- 背景：项目从本地美股驾驶舱起步，目标是记录真实持仓、股票池、模型评分和人工交易纪律。
- 变更：
  - 建立 Next.js 前端和 FastAPI 后端。
  - 增加驾驶舱、策略模型、股票池、持仓纪律、模型分析等页面。
  - 支持 ZA Bank/uSMART 持仓截图或手工记录导入。
  - 支持线下交易记录写入持仓纪律。
  - 股票池开始接入 FMP/Yahoo/AKShare 等真实或缓存行情。
  - 增加 PE/PEG/ROI 三类策略模型和基础回测。
  - 增加账户余额、现金垫、配舱建议和持仓盈亏计算。
- 验证：本地前后端可运行，核心接口可返回数据。
- 上线：后续随生产部署上线。
- 后续：逐步升级为真实行情、真实缓存、低价股候选、盯盘研判和配仓策略。
