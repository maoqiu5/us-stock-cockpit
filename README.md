# 美股驾驶舱

本项目实现一个本地可运行的自动化美股策略交易实验平台，形态参考小红书截图里的深色驾驶舱，但使用自有名称和代码结构。

## 已实现

- Next.js 前台：驾驶舱、策略模型、MAG7 股票池、持仓纪律、模型分析。
- FastAPI 后台：计划里的 REST API、样例数据、PE/PEG/ROI 因子策略、回测结果、风控状态。
- 风控引擎：单票 5%、总仓 50%、日亏 2%、周亏 6%、暂停自动执行。
- 券商适配层：`PaperBrokerAdapter`、`USmartBrokerAdapter` 和 `IBKRBrokerAdapter`。
- 实盘保护：任何 live 模式必须显式设置 `ENABLE_LIVE_TRADING=true`，订单仍会先经过风控。
- uSMART 请求预演：`POST /orders/preview` 会生成官方字段、请求头、签名状态和阻断原因。
- ZA Bank 手工执行记录：`POST /manual-executions` 用于把 ZA App 内确认的成交写回纪律日志。
- 当前主路径：AKShare 实时/准实时行情、TuShare 基本面、ZA/uSMART 结单或截图导入对账。

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

## 实盘接入方式

第一阶段按你的现有账户优先级设计：

1. **香港盈立/uSMART：优先实盘路径。** 官方 Open API 支持行情、账户和交易接口，美股交易类别为 `exchangeType=5`，限价单 `entrustProp=0`，市价单 `entrustProp=w`。
2. **ZA Bank/众安：手工或只读路径。** 公开资料确认 App 内可交易美股，但公开 Open Banking 页面未确认股票下单 API，因此不做逆向、不做自动点击。
3. **IBKR：备用路径。** 如果 uSMART API 权限申请不顺或稳定性不够，再接 IBKR TWS/IB Gateway。

## 当前现实路径

uSMART Open API 需要公司或渠道资质后，本项目主线调整为：

```text
AKShare 美股报价
  + TuShare 基本面/历史
  + ZA/uSMART 结单、截图、CSV、手工记录导入
  → 本地策略、风控、持仓、成交、PnL 和纪律复盘
```

新增接口：

```bash
curl http://127.0.0.1:8000/market/quotes
curl http://127.0.0.1:8000/data-sources/status
curl http://127.0.0.1:8000/portfolio/holdings
```

导入券商记录：

```bash
curl -X POST http://127.0.0.1:8000/imports/broker-records \
  -H 'Content-Type: application/json' \
  -d '{"broker":"usmart","records":[{"broker":"usmart","record_type":"holding","ticker":"NVDA","qty":3,"price":164.8,"executed_at":"07/06 15:20","note":"uSMART 持仓页手工导入"}]}'
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
  -d '{"ticker":"META","side":"BUY","qty":1,"order_type":"LMT","limit_price":712.4,"dry_run":false}'
```

### ZA Bank / 众安

当前版本把 ZA Bank 标记为 `za-manual`：系统生成信号、风控建议、限价单参数和纪律记录，你在 ZA App 内人工确认下单。除非 ZA Bank 官方提供投资交易 API，否则不做 App 自动点击或非公开接口。

记录 ZA App 手工成交：

```bash
curl -X POST http://127.0.0.1:8000/manual-executions \
  -H 'Content-Type: application/json' \
  -d '{"broker":"za-bank","ticker":"META","side":"BUY","qty":1,"price":712.4,"executed_at":"07/06 15:10","note":"ZA Bank App 手工确认"}'
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
