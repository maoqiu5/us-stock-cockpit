from __future__ import annotations

import os
import time
import json
import base64
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4
from typing import Union

import httpx

from .models import BrokerCapability, ExecutionConfig, OrderRequest, PreparedBrokerRequest, Side, TradeOrder


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
        self.order_path = os.getenv("USMART_ORDER_PATH", "/stock-trade/entrust")

    def place_order(self, request: OrderRequest) -> TradeOrder:
        if self.live and os.getenv("ENABLE_LIVE_TRADING") != "true":
            return self._blocked(request, "LIVE_DISABLED")
        if request.dry_run:
            return self._blocked(request, "DRY_RUN")

        prepared = self.prepare_order(request)
        if not prepared.ready_to_submit:
            return self._blocked(request, "USMART_" + "_".join(prepared.blockers))
        if os.getenv("USMART_ALLOW_NETWORK_SUBMIT") != "true":
            return self._blocked(request, "USMART_NETWORK_SUBMIT_DISABLED")

        try:
            response = httpx.post(prepared.url, headers=prepared.headers, json=prepared.body, timeout=10)
            body = response.json()
        except Exception as exc:
            return self._blocked(request, f"USMART_HTTP_ERROR:{exc.__class__.__name__}")

        if response.status_code >= 400 or body.get("code") not in {0, "0", None}:
            return self._blocked(request, f"USMART_REJECTED:{body.get('msg', response.status_code)}")

        data = body.get("data") or {}
        return TradeOrder(
            id=f"usmart_{data.get('entrustId', uuid4().hex[:8])}",
            broker="usmart-live" if self.live else "usmart-paper",
            ticker=request.ticker,
            side=request.side,
            qty=request.qty,
            order_type=request.order_type,
            limit_price=request.limit_price,
            status=str(data.get("statusName") or data.get("status") or "SUBMITTED"),
            created_at=datetime.utcnow().strftime("%m/%d %H:%M"),
        )

    def prepare_order(self, request: OrderRequest) -> PreparedBrokerRequest:
        body = self._entrust_payload(request)
        blockers = self._credential_blockers()
        headers = self._headers(body) if not blockers else self._unsigned_headers()
        if self.live and os.getenv("ENABLE_LIVE_TRADING") != "true":
            blockers.append("LIVE_DISABLED")
        return PreparedBrokerRequest(
            broker="usmart-live" if self.live else "usmart-paper",
            url=f"{self.base_url.rstrip('/')}{self.order_path}",
            method="POST",
            headers=headers,
            body=body,
            ready_to_submit=not blockers,
            blockers=blockers,
        )

    def _entrust_payload(self, request: OrderRequest) -> dict[str, Union[str, int, float, bool]]:
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

    def _headers(self, body: dict[str, Union[str, int, float, bool]]) -> dict[str, str]:
        request_id = str(int(time.time() * 1000000)).ljust(30, "0")[:30]
        timestamp = str(int(time.time() * 1000))
        body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        row_content = "".join([self.authorization, self.channel, "1", request_id, timestamp, body_text])
        return {
            "Authorization": self.authorization,
            "Content-Type": "application/json;charset=UTF-8",
            "X-Lang": "1",
            "X-Channel": self.channel,
            "X-Time": timestamp,
            "X-Request-Id": request_id,
            "X-Dt": "t5",
            "X-Sign": self._sign(row_content),
        }

    def _unsigned_headers(self) -> dict[str, str]:
        return {
            "Authorization": "***" if self.authorization else "",
            "Content-Type": "application/json;charset=UTF-8",
            "X-Lang": "1",
            "X-Channel": self.channel,
            "X-Time": "",
            "X-Request-Id": "",
            "X-Dt": "t5",
            "X-Sign": "",
        }

    def _credential_blockers(self) -> list[str]:
        blockers = []
        if not self.channel:
            blockers.append("CHANNEL_MISSING")
        if not self.authorization:
            blockers.append("AUTHORIZATION_MISSING")
        if not self.private_key_path:
            blockers.append("PRIVATE_KEY_PATH_MISSING")
        elif not os.path.exists(self.private_key_path):
            blockers.append("PRIVATE_KEY_NOT_FOUND")
        return blockers

    def _sign(self, row_content: str) -> str:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        with open(self.private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(key_file.read(), password=None)
        signature = private_key.sign(row_content.encode("utf-8"), padding.PKCS1v15(), hashes.MD5())
        return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")

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
