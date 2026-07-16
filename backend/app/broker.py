from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4

from .models import BrokerCapability, ExecutionConfig, OrderRequest, Side, TradeOrder


class BrokerAdapter(ABC):
    @abstractmethod
    def place_order(self, request: OrderRequest) -> TradeOrder:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def place_order(self, request: OrderRequest) -> TradeOrder:
        return TradeOrder(
            id=f"paper_{uuid4().hex[:8]}",
            broker="paper",
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status="DRY_RUN" if request.dry_run else "PAPER_SUBMITTED",
            created_at=datetime.utcnow().strftime("%m/%d %H:%M"),
        )


class USmartBrokerAdapter(BrokerAdapter):
    def __init__(self, live: bool = False):
        self.live = live
        self.base_url = os.getenv(
            "USMART_BASE_URL",
            "https://open-jy.yxzq.com" if live else "http://open-jy-uat.yxzq.com",
        )
        self.channel = os.getenv("USMART_CHANNEL", "")
        self.authorization = os.getenv("USMART_AUTHORIZATION", "")
        self.private_key_path = os.getenv("USMART_PRIVATE_KEY_PATH", "")

    def place_order(self, request: OrderRequest) -> TradeOrder:
        if self.live and os.getenv("ENABLE_LIVE_TRADING") != "true":
            return self._blocked(request, "LIVE_DISABLED")
        if request.dry_run:
            return self._blocked(request, "DRY_RUN")
        if not self.channel or not self.authorization or not self.private_key_path:
            return self._blocked(request, "USMART_CREDENTIALS_MISSING")

        payload = self._entrust_payload(request)
        # The official API requires RSA X-Sign over the body. We keep the real
        # order shape here, but block network submission until signing is wired
        # with the user's issued channel keys.
        if os.getenv("USMART_SIGNING_READY") != "true":
            return self._blocked(request, f"USMART_SIGNING_NOT_CONFIGURED:{payload['serialNo']}")

        return self._blocked(request, "USMART_NETWORK_CLIENT_PENDING")

    def _entrust_payload(self, request: OrderRequest) -> dict[str, str | int | float | bool]:
        return {
            "serialNo": int(time.time() * 1000),
            "entrustAmount": request.qty,
            "entrustPrice": 0 if request.order_type == "MKT" else request.limit_price,
            "entrustProp": "w" if request.order_type == "MKT" else "0",
            "entrustType": 0 if request.side == Side.buy else 1,
            "exchangeType": 5,
            "stockCode": request.ticker,
            "forceEntrustFlag": False,
        }

    def _blocked(self, request: OrderRequest, status: str) -> TradeOrder:
        return TradeOrder(
            id=f"usmart_{uuid4().hex[:8]}",
            broker="usmart-live" if self.live else "usmart-paper",
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status=status,
            created_at=datetime.utcnow().strftime("%m/%d %H:%M"),
        )


class IBKRBrokerAdapter(BrokerAdapter):
    def __init__(self, live: bool = False):
        self.live = live
        self.host = os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(os.getenv("IBKR_PORT", "7497"))
        self.client_id = int(os.getenv("IBKR_CLIENT_ID", "17"))

    def place_order(self, request: OrderRequest) -> TradeOrder:
        if self.live and os.getenv("ENABLE_LIVE_TRADING") != "true":
            return self._blocked(request, "LIVE_DISABLED")
        if request.dry_run:
            return self._blocked(request, "DRY_RUN")

        try:
            from ib_insync import IB, LimitOrder, MarketOrder, Stock  # type: ignore
        except Exception:
            return self._blocked(request, "IB_INSYNC_NOT_INSTALLED")

        # This path is intentionally narrow: no account secrets are stored here,
        # and IB Gateway/TWS must already be running with the user's session.
        ib = IB()
        ib.connect(self.host, self.port, clientId=self.client_id, timeout=10)
        contract = Stock(request.ticker, "SMART", "USD")
        order = (
            LimitOrder(request.side.value, request.qty, request.limit_price)
            if request.order_type == "LMT"
            else MarketOrder(request.side.value, request.qty)
        )
        trade = ib.placeOrder(contract, order)
        ib.sleep(1)
        status = trade.orderStatus.status or "SUBMITTED"
        ib.disconnect()
        return TradeOrder(
            id=f"ibkr_{trade.order.orderId}",
            broker="ibkr-live" if self.live else "ibkr-paper",
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status=status,
            created_at=datetime.utcnow().strftime("%m/%d %H:%M"),
        )

    def _blocked(self, request: OrderRequest, status: str) -> TradeOrder:
        return TradeOrder(
            id=f"ibkr_{uuid4().hex[:8]}",
            broker="ibkr-live" if self.live else "ibkr-paper",
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status=status,
            created_at=datetime.utcnow().strftime("%m/%d %H:%M"),
        )


def execution_config() -> ExecutionConfig:
    mode = os.getenv("BROKER_MODE", "paper")
    if mode not in {"paper", "usmart-paper", "usmart-live", "ibkr-paper", "ibkr-live", "za-manual"}:
        mode = "paper"
    return ExecutionConfig(
        mode=mode,  # type: ignore[arg-type]
        live_trading_enabled=os.getenv("ENABLE_LIVE_TRADING") == "true",
        ibkr_host=os.getenv("IBKR_HOST", "127.0.0.1"),
        ibkr_port=int(os.getenv("IBKR_PORT", "7497")),
        ibkr_client_id=int(os.getenv("IBKR_CLIENT_ID", "17")),
        usmart_base_url=os.getenv("USMART_BASE_URL", "http://open-jy-uat.yxzq.com"),
        usmart_channel=os.getenv("USMART_CHANNEL", ""),
        notes=[
            "paper 模式不会触达券商。",
            "uSMART/盈立是当前优先实盘路径；官方 Open API 支持美股交易，但需要申请渠道、token 和 RSA 签名。",
            "ZA Bank 当前按手工/只读通道处理，公开 Open Banking 资料未显示股票下单 API。",
            "ibkr-paper 需要本机 IB Gateway/TWS paper session 已登录。",
            "ibkr-live 还需要 ENABLE_LIVE_TRADING=true，且每个订单先通过风控引擎。",
        ],
    )


def broker_from_env() -> BrokerAdapter:
    mode = execution_config().mode
    if mode == "usmart-paper":
        return USmartBrokerAdapter(live=False)
    if mode == "usmart-live":
        return USmartBrokerAdapter(live=True)
    if mode == "ibkr-paper":
        return IBKRBrokerAdapter(live=False)
    if mode == "ibkr-live":
        return IBKRBrokerAdapter(live=True)
    return PaperBrokerAdapter()


def broker_capabilities() -> list[BrokerCapability]:
    return [
        BrokerCapability(
            id="usmart",
            name="香港盈立 uSMART",
            status="tradable",
            supports_us_stock_orders=True,
            integration="Open API: 行情、账户、交易；美股 exchangeType=5；限价单 entrustProp=0，市价单 entrustProp=w。",
            notes=["需要已开户且有资产", "需要申请 Open API 渠道", "需要 Authorization、X-Channel、X-Sign RSA 签名"],
        ),
        BrokerCapability(
            id="za-bank",
            name="ZA Bank 众安银行",
            status="manual",
            supports_us_stock_orders=False,
            integration="公开资料确认 App 内美股交易；公开 Open Banking 产品未确认股票下单接口。",
            notes=["先做持仓/资金手动录入或对账", "不逆向 App，不做自动点击下单", "若官方提供投资交易 API 后再升级适配器"],
        ),
        BrokerCapability(
            id="ibkr",
            name="Interactive Brokers",
            status="backup",
            supports_us_stock_orders=True,
            integration="TWS / IB Gateway API 备用路径。",
            notes=["适合长期自动化", "需要单独开户和本机网关会话", "可作为 uSMART 不稳定时的备用执行层"],
        ),
    ]
