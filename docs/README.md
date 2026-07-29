# 美股驾驶舱文档入口

## 项目说明

美股驾驶舱是 BrianHub 下的个人投资管理工具，用于集中查看真实持仓、账户现金、股票池、候选股、模型评分、配舱建议、线下交易记录和交易纪律。

线上入口：
- 前端：`https://brianhub.net/usstock`
- API：`https://brianhub.net/usstock/api/*`
- VPS 目录：`/root/apps/us-stock-cockpit`

## 当前有效文档

- [产品说明](./PRD.md)
- [部署说明](./DEPLOYMENT.md)
- [变更记录](./CHANGELOG.md)
- [项目交接说明](./PROJECT_HANDOFF.md)
- [AI 接力上下文](./AI_RESUME_CONTEXT.md)

## 专题文档

- [中长期股票池策略实施计划](./2026-07-23-long-term-watchlist-strategy.md)
- [BrianHub 多项目部署指南](./BRIANHUB_MULTI_PROJECT_GUIDE.md)

## 跨项目规则

- BrianHub 通用开发规则：`/root/apps/portal/docs/BRIANHUB_DEVELOPMENT_STANDARD.md`
- BrianHub 新项目文档要求：`/root/apps/portal/docs/NEW_PROJECT_DOCUMENTATION_REQUIREMENTS.md`
- BrianHub 新项目接入提示词：`/root/apps/portal/docs/NEW_PROJECT_ONBOARDING_PROMPT.md`

## 文档职责

- `docs/PRD.md`：当前产品边界、功能范围、数据原则和路线图。
- `docs/DEPLOYMENT.md`：VPS 部署、环境变量、数据目录、网关边界、验证和回滚。
- `docs/CHANGELOG.md`：正式版本记录。
- `docs/PROJECT_HANDOFF.md`：给新开发者或新 AI 会话的交接说明。
- `docs/AI_RESUME_CONTEXT.md`：较详细的 AI 接力上下文。

根目录 `README.md` 和 `CHANGELOG.md` 仍保留，用于兼容项目根入口；门户文档中心优先阅读 `docs/` 下的标准文档。

## 数据和敏感信息边界

以下内容不得进入 Git 或门户文档中心：

- `.env.production`
- `.app_password`
- `LOCAL_SECRETS.md`
- `data/`
- `logs/`
- `runtime/`
- 真实 API Key、服务器密码、网页访问密码、Cookie、内部令牌或券商私钥

## 维护规则

- 功能、算法、数据源、部署或重要文档变化，先更新 `docs/CHANGELOG.md`。
- 影响产品边界、路线图或数据原则时，同步更新 `docs/PRD.md`。
- 部署、环境变量、数据目录、回滚方式变化时，同步更新 `docs/DEPLOYMENT.md`。
- 不在文档中写真实密钥；环境变量只写变量名、用途和保存位置。
