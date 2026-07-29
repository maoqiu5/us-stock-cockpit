# 美股驾驶舱上线部署说明

目标：把本地 Next.js 前端、FastAPI 后端、账户状态文件和行情缓存部署到 VPS。公网 HTTPS 入口由独立 `brianhub-gateway` 项目统一管理。

## 推荐架构

- `frontend`：Next.js 页面，生产构建挂载在 `/usstock`，API 使用 `/usstock/api`。
- `backend`：FastAPI 服务，读取并写入 `/app/data/usstock/` 下的美股专属数据。
- `brianhub-gateway`：统一入口，自动申请 HTTPS 证书。
  - `https://brianhub.net/` -> 跳转到 `/usstock`
  - `https://brianhub.net/usstock` -> 美股前端
  - `https://brianhub.net/usstock/api/*` -> 美股后端

美股项目自身不再启动 Caddy，也不监听服务器 `80/443`。

## 重要安全设置

公网部署必须设置：

- `APP_PASSWORD`：历史项目内网页访问密码。接入 BrianHub 门户 SSO 后应逐步废弃项目内独立密码。
- `FMP_API_KEY`：行情 API Key，只写到服务器环境变量或 `.env.production`，不要提交到 Git。
- `ENABLE_LIVE_TRADING`：实盘下单开关。当前平台只做分析和手工交易记录，默认保持关闭。

## 服务器准备

任意支持 Docker 的 VPS 都可以，例如 Ubuntu 22.04/24.04。

服务器 `80/tcp` 和 `443/tcp` 只由 `brianhub-gateway` 监听。美股项目只需要加入外部 Docker 网络 `brianhub_edge`。

安装 Docker 和 Compose 后，把项目放到服务器，例如：

```bash
mkdir -p ~/apps
cd ~/apps
git clone <你的仓库地址> us-stock-cockpit
cd us-stock-cockpit
```

如果暂时没有 Git 仓库，可以先从本机同步整个项目目录到服务器，但不要把 `.env`、`.venv`、`node_modules`、`.next` 当成部署依赖。

## 配置环境变量

在服务器项目根目录创建 `.env.production`：

```bash
cp .env.production.example .env.production
```

填写变量名和用途，真实值只保存在 VPS，不写入文档：

| 变量名 | 用途 |
| --- | --- |
| `PUBLIC_URL` | 公网基础地址。 |
| `APP_PASSWORD` | 历史项目内访问密码，门户 SSO 完成后逐步废弃。 |
| `FMP_API_KEY` | FMP 行情和基本面 API Key。 |
| `BROKER_MODE` | 券商模式，当前以 paper/manual 为主。 |
| `ENABLE_LIVE_TRADING` | 是否允许真实网络下单，当前默认关闭。 |
| `DATABASE_PATH` | SQLite 数据库路径。 |
| `LOCAL_STATE_PATH` | JSON 状态镜像路径。 |
| `MARKET_CACHE_DIR` | 行情和候选股缓存目录。 |

## 数据库与本地数据

当前推荐使用 SQLite，数据库文件为：

- `data/usstock/usstock_cockpit.db`

数据库会保存：

- 持仓、订单、账户现金、纪律事件、股票池、黄金手工交易
- 每日行情缓存
- 历史收盘缓存
- 候选股筛选缓存

项目仍会保留 JSON 镜像，方便人工检查和迁移：

- `data/usstock/local_state.json`
- `data/usstock/market_cache/`

首次启动时，如果 `data/usstock/usstock_cockpit.db` 没有主状态，后端会自动从 `data/usstock/local_state.json` 导入并写入 SQLite。

也可以手动迁移：

```bash
python scripts/migrate_json_to_sqlite.py
```

部署前把本机的 `data/` 同步到服务器项目根目录：

```bash
rsync -av data/ user@server:~/apps/us-stock-cockpit/data/
```

上线后容器会把 `./data` 挂载到后端 `/app/data`，后续新增的交易记录、每日行情缓存都会写回服务器工作区和 SQLite 数据库。

## 启动

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build backend frontend
```

查看状态：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend
```

健康检查：

```bash
curl https://brianhub.net/usstock/api/health
```

浏览器打开：

```text
https://brianhub.net/usstock
```

当前 BrianHub 统一门户已作为长期登录入口。若项目内历史密码仍存在，只作为兼容层保留；后续应以门户 SSO 为准。

## 更新代码

手动发布：

```bash
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build backend frontend
```

或者直接运行：

```bash
scripts/deploy_prod.sh
```

建议后续接 GitHub 私有仓库和 GitHub Actions，让推送到 `main` 后自动 SSH 到服务器执行这个脚本。

## 备份

至少每天备份一次服务器上的美股数据目录：

```bash
scripts/backup_data.sh
```

备份会生成：

- `data/usstock/backups/usstock_cockpit-时间.db`
- `data/usstock/backups/usstock-data-时间.tar.gz`

建议把 `data/usstock/backups/` 同步回本机或网盘。`data/usstock/usstock_cockpit.db` 是美股核心数据库，`data/usstock/local_state.json` 是辅助镜像。

服务器上可以加 crontab：

```cron
10 6 * * * cd /root/apps/us-stock-cockpit && scripts/backup_data.sh >> data/usstock/backups/backup.log 2>&1
```

## 回滚

回滚前先确认最近备份：

```text
/root/apps/us-stock-cockpit/data/usstock/backups/
```

通用回滚步骤：

1. 停止或重建当前 backend/frontend 容器。
2. 恢复上一版代码文件或镜像。
3. 如涉及数据变更，恢复 `data/usstock/` 下的数据库和状态文件备份。
4. 重启业务容器。
5. 验证 `/usstock`、`/usstock/api/health`、`/usstock/api/watchlist` 和关键持仓/候选股接口。
6. 将回滚原因、影响范围和验证结果写入 `docs/CHANGELOG.md` 或 `docs/reports/`。

## 常见问题

### 打开网页但没有数据

检查后端日志：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f backend
```

检查 `.env.production` 是否包含行情数据源、历史兼容密码和数据目录相关变量。不要把真实值复制到文档或对话里。

### 密码一直不通过

如果仍使用项目内历史密码，确认浏览器输入的是服务器 `.env.production` 中的密码。修改密码后重启：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml restart backend
```

### HTTPS 证书或路由异常

到 `/root/apps/brianhub-gateway` 检查 Caddy 日志。美股项目不再持有 TLS 和 Caddy 配置。

### 数据没有持久化

确认 `docker-compose.prod.yml` 里后端有：

```yaml
volumes:
  - ./data:/app/data
```

并确认服务器项目目录下的 `data/` 可写，且环境变量包含数据库路径、状态镜像路径和行情缓存目录。真实路径值以 VPS `.env.production` 和 `docker-compose.prod.yml` 为准。
