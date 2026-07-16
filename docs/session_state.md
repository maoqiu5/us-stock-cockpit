# 美股驾驶舱会话状态

更新时间：2026-07-16 21:46 Asia/Shanghai

## 项目目标

搭建一个本地优先的自动化美股策略交易平台，前台参考截图里的深色驾驶舱形态，系统名为“美股驾驶舱”。当前定位是策略、风控、回测、持仓纪律、黄金盯盘和线下交易记录，不接管账户密码，不直接自动实盘下单。

## 当前技术栈

- 前端：Next.js / React，入口为 `app/page.tsx`
- 后端：FastAPI，入口为 `backend/app/main.py`
- 策略与黄金逻辑：
  - `backend/app/strategy.py`
  - `backend/app/gold_monitor.py`
- 本地可变数据：`data/local_state.json`
- 本地数据保护：`data/.gitignore` 忽略所有真实运行数据，只提交 `.gitignore`

## 本地服务

- 前端地址：http://127.0.0.1:3000
- 后端地址：http://127.0.0.1:8000
- 后端健康检查：http://127.0.0.1:8000/health

常用启动命令：

```bash
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node_modules/.bin/next dev --hostname 127.0.0.1 --port 3000
```

## 已实现功能

- 驾驶舱：首页指标、核心流程、纪律检查、风控状态、订单、数据源、券商接入路径
- 策略模型：PE_v1、PEG_v1、ROI_v1 展示与回测入口
- 股票池：支持新增和删除；新增时校验股票代码，成功后拉取行情参数
- 持仓纪律：展示当前 ZA Bank / uSMART 持仓、建议和风险
- 模型分析：支持策略、股票、日期区间、评测类型
- 黄金盯盘：民生积存金逻辑，参考建行公开积存金分时价
- 黄金线下记录：支持新增/删除线下买入记录，并纳入持仓收益、成本均价、剩余资金和策略建议
- 本地持久化：股票池、持仓、纪律事件、订单、黄金记录、暂停状态、昨收快照都会保存到 `data/local_state.json`

## 黄金盯盘规则

- 不再 10 秒实时刷新黄金金价
- 默认每 1 小时拉取一次真实积存金/黄金参考数据
- 点击“刷新黄金数据”时，强制刷新全部黄金页面数据，并更新策略建议
- 只合并真实公开源返回的分时点
- 宁愿缺失为空，也不虚构数据、不自行延展趋势线
- 当前 `refresh_seconds = 3600`

主要接口：

```text
GET  /gold/monitor
POST /gold/refresh
GET  /gold/manual-trades
POST /gold/manual-trades
DELETE /gold/manual-trades/{trade_id}
```

## 本地数据原则

用户明确要求：所有数据需要存在本地，不可丢失。

当前策略：

- 可变数据写入 `data/local_state.json`
- 写入采用临时文件替换，降低半写入风险
- `data/local_state.json` 不提交到 GitHub
- 测试已隔离到临时文件，不再污染真实本地状态

注意：之前黄金购买记录曾因后端内存重启丢失。该问题已修复，但已丢失的旧记录无法自动恢复，需要用户重新录入。

## 当前真实持仓基准

来自用户截图导入：

- uSMART：
  - NOK.US：99 股，成本 16.005，截图价 11.230
  - SMR.US：80 股，成本 19.23，截图价 8.360
- ZA Bank：
  - NOK：44 股，成本 16.1000，截图价 11.250
  - IAU：6 股，成本 85.6500，截图价 76.280
  - NVDA：0.0005 股，成本 220.0000，截图价 212.500

黄金：

- 产品：民生积存金
- 计划资金：10000 CNY
- 用户需要重新录入之前丢失的线下购买记录

## GitHub

- GitHub 用户：https://github.com/maoqiu5
- 仓库：https://github.com/maoqiu5/us-stock-cockpit
- 当前工作分支：`codex/us-stock-cockpit`
- 最近推送提交：
  - `8a0a73f` Throttle gold quote refresh
  - `340a7bd` Persist local trading state
  - `6602be7` Isolate tests from local state

注意：用户曾经在会话里粘贴过 GitHub PAT。不要保存、展示或复述 token；建议用户在 GitHub 设置中撤销旧 token。

## 验证记录

最近验证：

```bash
.venv/bin/pytest backend/tests
# 20 passed

PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node_modules/.bin/next build
# build passed
```

浏览器检查：

- 本地页面 `http://127.0.0.1:3000/` 可打开
- 没有 JS console error
- 驾驶舱主页面布局正常
- 已恢复为真实持仓摘要，不再显示测试行情快照

## 下一步建议

- 用户重新录入黄金线下购买记录
- 为本地状态增加“导出备份 / 恢复备份”按钮
- 增加状态文件自动备份，例如 `data/backups/local_state_YYYYMMDD_HHMMSS.json`
- 若用户指出具体前端渲染问题，按截图定位修复
