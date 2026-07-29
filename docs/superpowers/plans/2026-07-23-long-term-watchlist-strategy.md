# Long-Term Watchlist Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the stock pool into a medium/long-term investment cockpit with account-level cash settings and inline offline trade recording.

**Architecture:** Keep the current FastAPI + Next.js structure. Add a backend account cash update endpoint, change execution-plan generation so every configured account gets a visible buy/hold/sell plan, and update the watchlist UI with an inline modal for cash and trade entry.

**Tech Stack:** FastAPI/Pydantic backend, Next.js/React frontend, existing local state persistence, existing pytest and TypeScript checks.

## Global Constraints

- Do not sync or package production `data/`, `.env.production`, `.app_password`, or secrets.
- US stock project only deploys backend/frontend; do not modify gateway/Caddy.
- Every feature/algorithm/deployment update appends `CHANGELOG.md`; update `docs/PRD.md` when product behavior changes.
- Trading remains manual: the app records offline trades and refreshes data, never auto-submits broker orders.

---

### Task 1: Account Cash Settings

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_strategy_and_risk.py`

**Interfaces:**
- Produces: `AccountCashUpdateRequest(broker, available_cash, note)`
- Produces: `POST /portfolio/account-balances/{broker}` returning `AccountBalance`

- [ ] Add a failing backend test that updates ZA Bank cash and verifies `_account_balances()` returns the new amount.
- [ ] Run the targeted test and confirm it fails because the endpoint/model does not exist.
- [ ] Add the request model and endpoint; persist with `_save_local_state()`.
- [ ] Run the targeted test and confirm it passes.

### Task 2: Account-Level Long-Term Execution Plans

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_strategy_and_risk.py`

**Interfaces:**
- Produces: `execution_plan()` returns a plan for each non-empty account for unheld watchlist tickers.
- Produces: reasons/action text use medium/long-term language: phased entry, target allocation, valuation/position discipline.

- [ ] Add a failing test where ZA Bank and uSMART both have cash and an unheld BUY ticker exists; assert both accounts receive a plan.
- [ ] Add a failing test asserting plan copy uses medium/long-term language, not short-term chasing language.
- [ ] Implement account candidate selection for all accounts with account total or cash.
- [ ] Adjust action/reason copy and target-weight logic toward phased medium/long-term investing.
- [ ] Run tests and confirm they pass.

### Task 3: Inline Watchlist Offline Trade Modal

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/globals.css`

**Interfaces:**
- Consumes: existing `submitOfflineTrade(form)`.
- Produces: row-level “记录交易” action in stock pool.
- Produces: modal prefilled with ticker, account, side, quantity, reference price, executed time, note.

- [ ] Add component state for selected trade form in `WatchlistView`.
- [ ] Add a “记录交易” button per stock row.
- [ ] Render a modal form when selected; submit via existing `submitOfflineTrade`, then close and refresh through the existing `load()`.
- [ ] Add compact modal styles matching existing panels.
- [ ] Run TypeScript check.

### Task 4: Docs, Changelog, Sync, Verify

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/PRD.md`

**Interfaces:**
- Produces: new top CHANGELOG entry for long-term strategy, account cash setting, inline trade modal.

- [ ] Append `CHANGELOG.md`.
- [ ] Update PRD stock pool and offline trade scope.
- [ ] Run backend compile/tests and TypeScript check.
- [ ] Sync changed files to VPS with `cnstock_vps`, excluding data/secrets.
- [ ] Rebuild backend/frontend containers.
- [ ] Verify `/usstock`, `/api/health`, `/api/execution/plan`, and `/api/portfolio/account-balances` return 200.
