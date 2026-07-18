# Brianhub 多项目部署接入说明

本文档用于新的 AI 会话快速理解 `brianhub.net` 的部署边界。核心原则：一个域名可以挂多个项目，但每个项目必须有独立路径、独立数据目录、独立数据库、独立 Docker 命名空间。

## 当前线上项目

| 项目 | 路径 | 服务器目录 | 数据目录 | 数据库 | API |
| --- | --- | --- | --- | --- | --- |
| 美股驾驶舱 | `/usstock` | `/root/apps/us-stock-cockpit` | `/root/apps/us-stock-cockpit/data/usstock` | `usstock_cockpit.db` | `/usstock/api/*` |

当前公开入口：

- 美股前端：`https://brianhub.net/usstock`
- 美股 API：`https://brianhub.net/usstock/api/*`
- 根路径：`https://brianhub.net/` 自动跳转到 `/usstock`

当前代码来源：

- GitHub 仓库：`https://github.com/maoqiu5/us-stock-cockpit.git`
- 生产分支：`main`
- 本机项目目录：`/Users/brian/Documents/美股`
- 服务器项目目录：`/root/apps/us-stock-cockpit`
- 服务器 Git remote：`git@github.com-usstock:maoqiu5/us-stock-cockpit.git`
- 服务器通过 GitHub deploy key 拉取代码；deploy key 放在服务器 `/root/.ssh/us_stock_cockpit_deploy`，不要复制到项目仓库。

当前生产访问密码：

- 访问密码只存服务器 `.env.production` 和 `.app_password`，不要写入 Git。
- 前端会把用户输入的密码保存在当前浏览器 `localStorage`，所以同一台电脑上再次打开可能不再弹登录。
- 页面顶部有“锁定”按钮，点击后会清除当前浏览器保存的密码，下次进入必须重新输入。

## 路径命名规则

每个项目必须先确定一个短 slug：

- 美股：`usstock`
- 示例项目：`demoapp`
- 黄金如果独立：`gold`
- 其他项目：使用小写英文、数字、短横线，不要使用中文路径

路径规则：

- 前端：`https://brianhub.net/<slug>`
- API：`https://brianhub.net/<slug>/api/*`
- 数据目录：`data/<slug>/`
- 数据库：`data/<slug>/<slug>_cockpit.db`，如果不是投资类项目，改成 `data/<slug>/<slug>.db`
- 备份：`data/<slug>/backups/`

禁止多个项目共用：

- 同一个 SQLite 文件
- 同一个 `local_state.json`
- 同一个 `market_cache/`
- 同一个 Docker Compose project name
- 同一个 Docker 网络别名

## 美股项目当前生产配置

`docker-compose.prod.yml` 中美股已经固定为：

```yaml
name: brianhub-usstock

services:
  backend:
    environment:
      DATABASE_PATH: /app/data/usstock/usstock_cockpit.db
      LOCAL_STATE_PATH: /app/data/usstock/local_state.json
      MARKET_CACHE_DIR: /app/data/usstock/market_cache
    networks:
      brianhub_edge:
        aliases:
          - usstock_backend

  frontend:
    build:
      args:
        NEXT_PUBLIC_API_BASE: /usstock/api
        NEXT_PUBLIC_BASE_PATH: /usstock
    networks:
      brianhub_edge:
        aliases:
          - usstock_frontend
```

`Caddyfile` 中美股路由：

```caddyfile
route /usstock/api/* {
    uri strip_prefix /usstock/api
    reverse_proxy usstock_backend:8000
}

route /usstock* {
    reverse_proxy usstock_frontend:3000
}
```

## 新项目接入方式

以下使用 `demoapp` 作为占位示例。它只表示“未来某个新项目”，不是已经确定要上线的项目名称。

1. 新建独立项目目录，不要放进美股项目：

```bash
mkdir -p /root/apps/demoapp
```

2. 新项目使用独立 Compose name：

```yaml
name: brianhub-demoapp
```

3. 新项目数据路径必须独立：

```dotenv
DATABASE_PATH=/app/data/demoapp/demoapp.db
LOCAL_STATE_PATH=/app/data/demoapp/local_state.json
MARKET_CACHE_DIR=/app/data/demoapp/market_cache
```

4. 新项目前端构建参数：

```yaml
args:
  NEXT_PUBLIC_API_BASE: /demoapp/api
  NEXT_PUBLIC_BASE_PATH: /demoapp
```

5. 新项目接入共享 Docker 网络：

```yaml
networks:
  brianhub_edge:
    name: brianhub_edge
    external: true
```

并给服务设置唯一别名：

```yaml
backend:
  networks:
    brianhub_edge:
      aliases:
        - demoapp_backend

frontend:
  networks:
    brianhub_edge:
      aliases:
        - demoapp_frontend
```

6. 更新统一入口 Caddy，新增路由：

```caddyfile
route /demoapp/api/* {
    uri strip_prefix /demoapp/api
    reverse_proxy demoapp_backend:8000
}

route /demoapp* {
    reverse_proxy demoapp_frontend:3000
}
```

重要：当前 Caddy 运行在美股项目 Compose 内，已经占用服务器 `80/443`。后续新项目不要再启动自己的 Caddy 监听 `80/443`，否则端口会冲突。新项目只启动自己的 frontend/backend，并接入 `brianhub_edge` 网络，再让现有 Caddy 转发。

## GitHub 发布流程

当前已经跑通的短期发布方式是：本机提交到 GitHub，服务器手动拉取并重建容器。

本机修改后：

```bash
cd /Users/brian/Documents/美股
git status
git add 需要提交的文件
git commit -m "本次修改说明"
git push origin main
```

服务器发布：

```bash
ssh root@192.236.235.229
cd /root/apps/us-stock-cockpit
scripts/deploy_prod.sh
```

`scripts/deploy_prod.sh` 会执行：

- 拉取 GitHub `main` 最新代码。
- 构建 backend/frontend Docker 镜像。
- 重建美股项目容器。
- 保留服务器 `data/usstock/` 下的生产数据。

注意：

- 不要在服务器直接改业务代码，避免和 GitHub 版本分叉。
- 不要提交 `.env.production`、`.app_password`、`data/`、API key、服务器密码。
- 如果只改了文档，也建议走 GitHub 提交流程，让新的 AI 会话能从仓库读到最新说明。
- 后续可以升级成 GitHub Actions 或 webhook 自动部署，但当前稳定做法仍是手动 SSH 执行部署脚本。

## 发布后验证

每次发布美股项目后，至少检查以下几项：

```bash
curl -I https://brianhub.net/usstock
curl -I https://brianhub.net/
curl -s https://brianhub.net/usstock/api/health
curl -s -o /dev/null -w '%{http_code}\n' https://brianhub.net/usstock/api/portfolio/holdings
curl -s -o /dev/null -w '%{http_code}\n' -H 'x-app-password: 访问密码' https://brianhub.net/usstock/api/portfolio/holdings
```

预期：

- `/usstock` 返回 `200`。
- `/` 返回 `302` 并跳转到 `/usstock`。
- `/usstock/api/health` 返回 `{"status":"ok"}`。
- 未带密码的业务接口返回 `401`。
- 带密码的业务接口返回 `200`。

如果需要确认前端是否已经切到新构建，可以先抓取页面里的 Next.js 页面资源：

```bash
curl -sL https://brianhub.net/usstock | rg -o '/usstock/_next/static/chunks/app/page-[^" ]+\.js'
```

再检查该 JS 里是否包含本次改动的关键文本，例如“锁定”：

```bash
curl -sL https://brianhub.net/usstock/_next/static/chunks/app/page-文件名.js | rg '锁定|已锁定|us-stock-cockpit-password'
```

## 服务器边界

服务器项目目录建议：

```text
/root/apps/
  us-stock-cockpit/     # 美股，当前已上线
  demoapp/              # 示例：未来某个新项目
  gateway/              # 未来如果要抽离统一 Caddy，可放这里
```

当前阶段 Caddy 在：

```text
/root/apps/us-stock-cockpit/Caddyfile
```

未来项目上线时，只允许修改 Caddy 路由，不要移动或删除美股数据。

## 数据备份规则

每个项目只备份自己的数据目录。

美股备份：

```bash
cd /root/apps/us-stock-cockpit
scripts/backup_data.sh
```

默认备份：

```text
data/usstock/backups/
```

未来项目应有自己的备份脚本或设置：

```bash
PROJECT_SLUG=demoapp scripts/backup_data.sh
```

如果复用脚本，必须确认 `PROJECT_SLUG` 指向当前项目，不能把美股和其他项目打进同一个备份包。

## 发布检查清单

每次发布新项目或修改路由后检查：

```bash
docker network inspect brianhub_edge
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl -I https://brianhub.net/<slug>
curl https://brianhub.net/<slug>/api/health
```

需要密码保护的业务接口，再检查：

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://brianhub.net/<slug>/api/portfolio/holdings
curl -s -o /dev/null -w '%{http_code}\n' -H 'x-app-password: 密码' https://brianhub.net/<slug>/api/portfolio/holdings
```

预期：无密码业务接口返回 `401`，带密码返回 `200`。

如果前端打开后仍像旧版：

- 先确认 `scripts/deploy_prod.sh` 是否完整跑完。
- 再确认页面 HTML 中的 `page-*.js` 文件名是否变化。
- 浏览器可能缓存了旧资源时，强制刷新或用无痕窗口访问。
- 如果同一浏览器已经登录过，可能因为 `localStorage` 保存了密码而直接进入；点页面顶部“锁定”可清除本机授权。

## 不要做的事

- 不要把其他项目代码放进 `/root/apps/us-stock-cockpit`。
- 不要让其他项目读写 `data/usstock/`。
- 不要复用 `usstock_backend`、`usstock_frontend` 网络别名。
- 不要启动第二个监听 `80/443` 的 Caddy/Nginx。
- 不要删除 `data/usstock/usstock_cockpit.db`、`data/usstock/local_state.json`、`data/usstock/market_cache/`。
- 不要把 `.env.production`、API key、网站密码提交到 Git。
