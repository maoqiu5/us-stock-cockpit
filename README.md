# 美股驾驶舱

本项目实现一个可本地运行、也已部署到 `brianhub.net/usstock` 的美股策略与持仓纪律驾驶舱。系统用于记录真实持仓、线下成交、股票池、行情缓存、模型评分和配舱建议；当前保持人工确认交易，不做自动实盘下单。

线上入口：

- 美股驾驶舱：`https://brianhub.net/usstock`
- API 前缀：`https://brianhub.net/usstock/api`
- 根域名：`https://brianhub.net/` 自动跳转到 `/usstock`

生产访问受 `APP_PASSWORD` 保护。后端业务接口未带密码会返回 `401`；前端会在当前浏览器保存一次输入的密码，顶部“锁定”按钮可清除本机授权。

## 已实现

- Next.js 前台：驾驶舱、策略模型、股票池、持仓纪律、模型分析。
- FastAPI 后台：REST API、真实/缓存行情、PE/PEG/ROI 因子策略、回测结果、风控状态。
- SQLite 本地/云端持久化：持仓、订单、账户余额、股票池、黄金成交、行情缓存、纪律事件。
- 风控引擎：单票 5%、总仓 50%、日亏 2%、周亏 6%、暂停自动执行。
- 券商适配层：`PaperBrokerAdapter`、`USmartBrokerAdapter` 和 `IBKRBrokerAdapter`。
- 实盘保护：任何 live 模式必须显式设置 `ENABLE_LIVE_TRADING=true`，订单仍会先经过风控。
- uSMART 请求预演：`POST /orders/preview` 会生成官方字段、请求头、签名状态和阻断原因。
- ZA Bank/uSMART 手工执行记录：`POST /manual-executions` 用于把 App 内确认的成交写回纪律日志和持仓。
- 股票池配舱建议：结合当前行情、持仓、账户现金、现金垫比例和模型评分生成买入/卖出参考价。
- 当前主路径：FMP 行情、真实历史/缓存数据、ZA/uSMART 结单或截图导入对账；不使用模拟数据补齐生产判断。

## 项目结构

```text
app/                  # Next.js 前端
backend/app/          # FastAPI 后端、策略、风控、数据源、存储
backend/tests/        # 后端测试
scripts/              # 数据迁移、备份、生产部署脚本
docs/                 # 部署、交接、多项目接入说明
data/usstock/         # 本地数据目录，生产数据不提交 Git
```

关键文档：

- `docs/AI_RESUME_CONTEXT.md`：给新 AI 会话快速接手项目。
- `docs/DEPLOYMENT.md`：美股项目生产部署说明。
- `docs/BRIANHUB_MULTI_PROJECT_GUIDE.md`：`brianhub.net` 多项目部署边界和接入方式。

## 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

另开一个终端：

```bash
npm install
npm run dev
```

前台默认地址：`http://localhost:3000`

后台 API：`http://127.0.0.1:8000/docs`

本地开发默认可以不设置 `APP_PASSWORD`。如果要模拟生产鉴权，可以设置：

```bash
APP_PASSWORD=本地测试密码 uvicorn backend.app.main:app --reload --port 8000
```

带密码请求示例：

```bash
curl -H 'x-app-password: 本地测试密码' http://127.0.0.1:8000/portfolio/holdings
```

## 生产部署

当前生产部署在 VPS：

- 域名：`brianhub.net`
- 项目路径：`/usstock`
- 服务器目录：`/root/apps/us-stock-cockpit`
- GitHub 仓库：`https://github.com/maoqiu5/us-stock-cockpit.git`
- 生产分支：`main`

发布流程：

```bash
git add 需要提交的文件
git commit -m "本次修改说明"
git push origin main
```

然后登录服务器执行：

```bash
cd /root/apps/us-stock-cockpit
scripts/deploy_prod.sh
```

发布后验证：

```bash
curl -s https://brianhub.net/usstock/api/health
curl -s -o /dev/null -w '%{http_code}\n' https://brianhub.net/usstock/api/portfolio/holdings
curl -s -o /dev/null -w '%{http_code}\n' -H 'x-app-password: 访问密码' https://brianhub.net/usstock/api/portfolio/holdings
```

预期：健康检查返回 `{"status":"ok"}`，未带密码业务接口返回 `401`，带密码返回 `200`。

详细部署和后续新项目接入边界见 `docs/DEPLOYMENT.md` 与 `docs/BRIANHUB_MULTI_PROJECT_GUIDE.md`。

## 实盘接入方式

第一阶段按你的现有账户优先级设计：

1. **香港盈立/uSMART：优先实盘路径。** 官方 Open API 支持行情、账户和交易接口，美股交易类别为 `exchangeType=5`，限价单 `entrustProp=0`，市价单 `entrustProp=w`。
2. **ZA Bank/众安：手工或只读路径。** 公开资料确认 App 内可交易美股，但公开 Open Banking 页面未确认股票下单 API，因此不做逆向、不做自动点击。
3. **IBKR：备用路径。** 如果 uSMART API 权限申请不顺或稳定性不够，再接 IBKR TWS/IB Gateway。

## 当前现实路径

uSMART Open API 需要公司或渠道资质后，本项目当前主线为：

```text
FMP 行情和基础财务数据
  + 真实历史/缓存数据
  + ZA/uSMART 结单、截图、CSV、手工记录导入
  → 本地策略、风控、持仓、成交、PnL 和纪律复盘
```

新增接口：

```bash
curl http://127.0.0.1:8000/market/quotes
curl http://127.0.0.1:8000/data-sources/status
curl http://127.0.0.1:8000/portfolio/holdings
curl -X POST http://127.0.0.1:8000/market/import-previous-close
```

`/market/import-previous-close` 用于美股未开盘时导入上一交易日收盘价。接口会优先读取 Yahoo 最近日线；如果公开接口不可用，会回退到内置昨收快照，随后重估本地持仓、市值和持仓盈亏。
生产判断要求优先使用真实数据；缺少真实历史或行情时宁愿显示为空或数据质量不足，不用模拟数据补齐。

导入 uSMART 持仓截图：

```bash
curl -X POST http://127.0.0.1:8000/imports/usmart-screenshot \
  -H 'Content-Type: application/json' \
  -d '{"image_path":"/absolute/path/to/usmart_position.jpg","as_of":"07/16 14:02"}'
```

导入 ZA Bank 持仓截图：

```bash
curl -X POST http://127.0.0.1:8000/imports/za-screenshot \
  -H 'Content-Type: application/json' \
  -d '{"image_path":"/absolute/path/to/za_position.jpg","as_of":"07/16 14:04"}'
```

导入券商记录：

```bash
curl -X POST http://127.0.0.1:8000/imports/broker-records \
  -H 'Content-Type: application/json' \
  -d '{"broker":"usmart","records":[{"broker":"usmart","record_type":"holding","ticker":"NOK.US","qty":99,"price":11.23,"executed_at":"07/16 14:02","note":"uSMART 持仓页手工导入"}]}'
```

### uSMART / 香港盈立

先向 uSMART 申请 Open API。官方文档说明请求头需要 `Authorization`、`X-Channel`、`X-Time`、`X-Request-Id`、`X-Sign`，`X-Sign` 使用 MD5withRSA 后做 URL-safe base64。代码已经实现请求体映射和签名头生成；真实网络提交默认仍关闭。

```bash
BROKER_MODE=usmart-paper
USMART_BASE_URL=http://open-jy-uat.yxzq.com
USMART_CHANNEL=你的渠道号
USMART_AUTHORIZATION=你的token
USMART_PRIVATE_KEY_PATH=/absolute/path/to/private_key.pem
USMART_ORDER_PATH=/stock-trade/entrust
USMART_ALLOW_NETWORK_SUBMIT=false
```

Live trading 需要额外设置：

```bash
BROKER_MODE=usmart-live
USMART_BASE_URL=https://open-jy.yxzq.com
ENABLE_LIVE_TRADING=true
USMART_ALLOW_NETWORK_SUBMIT=true
```

在真实提交前，先用预演接口检查请求：

```bash
curl -X POST http://127.0.0.1:8000/orders/preview \
  -H 'Content-Type: application/json' \
  -d '{"ticker":"NOK.US","side":"BUY","qty":1,"order_type":"LMT","limit_price":11.23,"dry_run":false}'
```

### ZA Bank / 众安

当前版本把 ZA Bank 标记为 `za-manual`：系统生成信号、风控建议、限价单参数和纪律记录，你在 ZA App 内人工确认下单。除非 ZA Bank 官方提供投资交易 API，否则不做 App 自动点击或非公开接口。

记录 ZA App 手工成交：

```bash
curl -X POST http://127.0.0.1:8000/manual-executions \
  -H 'Content-Type: application/json' \
  -d '{"broker":"za-bank","ticker":"NOK","side":"BUY","qty":1,"price":11.25,"executed_at":"07/16 14:04","note":"ZA Bank App 手工确认"}'
```

### IBKR 备用

1. 在 IBKR TWS 或 IB Gateway 中登录 paper account。
2. 启用 API 连接并允许本机 `127.0.0.1`。
3. 设置环境变量：

```bash
BROKER_MODE=ibkr-paper
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=17
```

4. 安装 IBKR Python 依赖：

```bash
pip install ib-insync
```

5. 先调用 `/orders`，保持 `dry_run=true` 验证订单路径。

Live trading 需要额外设置：

```bash
BROKER_MODE=ibkr-live
IBKR_PORT=7496
ENABLE_LIVE_TRADING=true
```

即使开启 live，后端仍会先执行风控检查；超过单票、总仓、亏损停机或暂停自动执行时会返回 `BLOCKED`。

## 验证

```bash
pytest backend/tests
npm run build
```

如果本机 `pnpm/npm` 因网络或依赖状态检查失败，可以至少运行 TypeScript 检查：

```bash
PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/tsc --noEmit
```
