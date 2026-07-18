# 美股驾驶舱 AI 接力上下文

更新时间：2026-07-17  
工作区：`/Users/brian/Documents/美股`

这份文档给新的 AI 对话或接手开发者使用。目标是打开后立刻理解本项目、当前进度、用户正在做什么、下一步怎么继续。

## 1. 当前一句话状态

项目已经从本机美股驾驶舱升级到公网 VPS 临时上线阶段：前后端 Docker/Caddy 配置已补齐，访问密码已加入，SQLite 数据库已接入并完成本地 JSON 迁移。RackNerd VPS 已购买并部署成功，当前可通过服务器 IP 临时访问；域名/HTTPS 绑定仍待用户完成域名购买和 DNS 配置。

## 2. 用户目标

用户希望：

- 美股驾驶舱可以随时随地通过网页打开。
- 所有持仓、账户余额、交易记录、行情缓存和候选股数据都要持久保存。
- 数据既要能上云，也要能在工作区保留本地副本。
- 后续本地改代码后可以同步发布到云端。
- 不能使用模拟数据；数据缺失宁愿空着或显示数据质量不足。
- 黄金分析板块保留，不要破坏。

## 3. 当前购买进度

服务器：

- 推荐给用户的是 RackNerd VPS。
- 用户已购买 RackNerd VPS。
- 配置：
  - Ubuntu 24.04 64 Bit
  - 2 GB RAM
  - 2 CPU Cores
  - 1 IPv4 Included
  - 35 GB Disk
  - 服务器公网 IP：`192.236.235.229`
- 临时访问地址：`http://192.236.235.229`
- 已安装 Docker、Docker Compose v2、Git、rsync。
- 项目部署目录：`/root/apps/us-stock-cockpit`
- 线上访问密码存放在服务器：`/root/apps/us-stock-cockpit/.app_password`
- 不要把访问密码写进 Git 或文档。
- RackNerd 优惠码曾建议尝试：
  - `DRWOOKIEE`
  - `INTENSEINVESTOR`
  - `MYPHPNOTES`
- 注意：用户一开始在 shared hosting 页面，已提醒不要买 shared hosting，要买 VPS。

域名：

- 用户正在 Porkbun 购买域名。
- 建议优先买 `.com`。
- 解释过 Porkbun 的 `at cost` 是“按成本价出售”，可以继续买。
- Porkbun 优惠码曾建议尝试：
  - `VIKAS`
  - `MAKERTHRIVE25`
  - `MRKEHEL`
- 用户让想域名时，曾推荐：
  - `brianfolio.com`
  - `folioyard.com`
  - `stockdeck365.com`

新对话中，如果用户已经买完，请直接索要：

- 域名名称
- Porkbun DNS 是否可登录/可改 A 记录

## 4. 技术架构

前端：

- Next.js 15
- React 19
- TypeScript
- 入口：`app/page.tsx`
- 样式：`app/globals.css`
- 本地默认：`http://127.0.0.1:3000`

后端：

- FastAPI
- Pydantic
- 入口：`backend/app/main.py`
- 本地默认：`http://127.0.0.1:8000`

部署：

- `Dockerfile.frontend`
- `Dockerfile.backend`
- `docker-compose.prod.yml`
- `Caddyfile`
- 线上统一入口：
  - `https://brianhub.net/` -> 自动跳转到 `/usstock`
  - `https://brianhub.net/usstock` -> 美股前端
  - `https://brianhub.net/usstock/api/*` -> 美股后端

数据库与数据：

- SQLite 主库：`data/usstock/usstock_cockpit.db`
- JSON 镜像：`data/usstock/local_state.json`
- 行情缓存镜像：`data/usstock/market_cache/`
- 备份目录：`data/usstock/backups/`

## 5. 已完成的重要改造

公网访问保护：

- 后端新增 `APP_PASSWORD` 保护。
- 只有未设置 `APP_PASSWORD` 时，本地开发才不需要密码。
- 前端新增密码登录页，密码保存在浏览器 localStorage。
- 后端接口支持 `X-App-Password` 请求头。

SQLite 持久层：

- 新增：`backend/app/storage.py`
- 表：
  - `app_state`
  - `market_quotes`
  - `daily_closes`
  - `screening_payloads`
- 启动逻辑：
  - 优先从 SQLite 读取主状态。
  - 如果 SQLite 没有主状态，则从 `data/usstock/local_state.json` 导入并写入 SQLite。
  - 保存状态时同时写 SQLite 和 JSON 镜像。

缓存层：

- `backend/app/market_cache.py` 已接入 SQLite。
- 行情、历史收盘、候选股 payload 会写 SQLite，同时保留 JSON 镜像。

部署脚本：

- `scripts/deploy_prod.sh`
  - 服务器上执行 `git pull --ff-only`
  - 重新 build 并启动 Docker Compose
- `scripts/backup_data.sh`
  - 备份 SQLite
  - 打包 `data/`
  - 默认删除 30 天前备份
- `scripts/migrate_json_to_sqlite.py`
  - 把 `data/usstock/local_state.json` 导入 SQLite

服务器部署状态：

- Docker 镜像已成功构建。
- 容器已启动：
  - Compose project：`brianhub-usstock`
  - 网络别名：`usstock_backend`、`usstock_frontend`
- 外网测试已通过：
  - `curl -I https://brianhub.net/usstock` 返回 200。
  - `curl https://brianhub.net/usstock/api/health` 返回 `{"status":"ok"}`。
  - 未带密码访问持仓接口返回 401。
  - 带 `X-App-Password` 可读取账户余额。
- 已配置服务器每日备份：
  - crontab 需要使用：`10 6 * * * cd /root/apps/us-stock-cockpit && scripts/backup_data.sh >> data/usstock/backups/backup.log 2>&1`

部署文档：

- `docs/DEPLOYMENT.md`
- `docs/BRIANHUB_MULTI_PROJECT_GUIDE.md`

项目总交接：

- `docs/PROJECT_HANDOFF.md`

当前接力快照：

- `docs/AI_RESUME_CONTEXT.md`

## 6. 当前真实账户数据概况

最近从 uSMART 截图导入的最终状态：

uSMART：

- 现金：`762.93 USD`
- 持仓市值：`841.59 USD`
- 总资产：`1604.52 USD`
- `NOK.US` 已清仓
- 当前持仓：
  - `ALXO.US` 70 股，成本 `2.119`
  - `ACRS.US` 27 股，成本 `5.48`
  - `ABUS.US` 27 股，成本 `4.779`
  - `AMBP.US` 25 股，成本 `4.76`
  - `ABCL.US` 24 股，成本 `6.32`
  - `ABSI.US` 18 股，成本 `8.219`

ZA Bank：

- `NOK` 44 股，成本 `16.1`
- `IAU` 6 股，成本 `85.65`
- `NVDA` 0.0005 股，成本 `220`

验证过：

- 后端导入测试可从 SQLite 恢复 9 条持仓。
- `ACCOUNT_CASH_BALANCES` 中 uSMART 为 `762.93`。

## 7. 关键环境变量

本地开发：

```dotenv
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
NEXT_PUBLIC_BASE_PATH=
APP_PASSWORD=
FMP_API_KEY=
BROKER_MODE=paper
ENABLE_LIVE_TRADING=false
```

生产部署：

```dotenv
APP_DOMAIN=stock.example.com
PUBLIC_URL=https://stock.example.com
TLS_EMAIL=you@example.com
APP_PASSWORD=强密码
FMP_API_KEY=用户的FMPKey
DATABASE_PATH=/app/data/usstock/usstock_cockpit.db
LOCAL_STATE_PATH=/app/data/usstock/local_state.json
MARKET_CACHE_DIR=/app/data/usstock/market_cache
BROKER_MODE=paper
ENABLE_LIVE_TRADING=false
```

注意：

- 不要把真实 FMP key、服务器密码、APP_PASSWORD 写入 Git。
- 用户曾提供 FMP key，但不要写入文件。

## 8. 本地验证命令

Python 编译：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache .venv/bin/python -m py_compile backend/app/main.py backend/app/market_cache.py backend/app/storage.py scripts/migrate_json_to_sqlite.py
```

前端类型检查：

```bash
PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node_modules/.bin/tsc --noEmit
```

SQLite 状态检查：

```bash
.venv/bin/python -c "import sqlite3; conn=sqlite3.connect('data/usstock/usstock_cockpit.db'); print(conn.execute('select key, length(payload), updated_at from app_state').fetchall())"
```

后端加载检查：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex-pycache .venv/bin/python -c "from backend.app.main import HOLDINGS, ACCOUNT_CASH_BALANCES; print(len(HOLDINGS)); print(ACCOUNT_CASH_BALANCES)"
```

备份：

```bash
scripts/backup_data.sh
```

## 9. 本地启动命令

后端：

```bash
FMP_API_KEY='不要写入文件的真实key' .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
PATH=/Users/brian/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node_modules/.bin/next dev --hostname 127.0.0.1 --port 3000
```

如端口绑定被沙箱拦截，需要用授权方式运行。

## 10. 生产部署步骤

服务器已经部署完成。等用户买完域名后，按这个顺序绑定域名：

1. 在 Porkbun DNS 中添加 A 记录：
   - Host：`@`
   - Value：`192.236.235.229`
   - TTL：默认即可
2. 如需要 `www`，再添加：
   - Host：`www`
   - Type：`CNAME`
   - Value：`@`
3. 修改服务器 `.env.production`：

```bash
cd /root/apps/us-stock-cockpit
nano .env.production
```

把：

```dotenv
APP_DOMAIN=:80
PUBLIC_URL=http://192.236.235.229
```

改成：

```dotenv
APP_DOMAIN=brianhub.net
PUBLIC_URL=https://brianhub.net
```

当前线上美股项目挂载路径：

- 前端：`https://brianhub.net/usstock`
- API：`https://brianhub.net/usstock/api/*`
- 根路径：`https://brianhub.net/` 自动跳转到 `/usstock`

4. 重启：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

5. 检查：

```bash
curl https://用户域名.com/api/health
```

6. 浏览器打开 `https://用户域名.com`，输入 `APP_PASSWORD`。

## 11. 后续代码同步发布方案

推荐：

- 建 GitHub 私有仓库。
- 本地代码提交并 push。
- 服务器运行 `scripts/deploy_prod.sh`。

后续可升级为 GitHub Actions：

- push 到 `main` 后自动 SSH 到 VPS。
- 服务器执行：

```bash
cd ~/apps/us-stock-cockpit
scripts/deploy_prod.sh
```

数据不进 Git：

- `data/usstock/usstock_cockpit.db`
- `data/usstock/market_cache/`
- `data/usstock/backups/`

这些已经写入 `.gitignore`。

## 12. 需要小心的地方

- 不要提交真实账户数据、API key、服务器密码。
- 不要删除 `data/usstock/local_state.json`、`data/usstock/usstock_cockpit.db`、`data/usstock/market_cache/`。
- 不要启用 `ENABLE_LIVE_TRADING=true`，除非用户明确要求并完成额外风控确认。
- 不要使用模拟数据补回测和候选股。
- 如果手工改了 `data/usstock/local_state.json`，需要同步迁移到 SQLite 或让后端首次启动导入；当前更推荐通过 API 或脚本迁移。
- `tsc --noEmit` 会生成 `tsconfig.tsbuildinfo`，检查后要删除。
- 本机没有 Docker，无法本地实际跑 Compose，只能做代码和配置检查。

## 13. 最近验证结果

最近已验证：

- `scripts/migrate_json_to_sqlite.py` 成功。
- SQLite `app_state` 中存在 `main`。
- 后端导入测试读到 9 条持仓。
- uSMART 现金为 `762.93`。
- `scripts/backup_data.sh` 成功生成备份。
- Python 编译通过。
- TypeScript 检查通过。
- VPS 临时上线成功：`http://192.236.235.229`。

当前工作树有许多未提交改动，包括部署、数据库、UI 认证和之前业务优化。不要随意 revert。
